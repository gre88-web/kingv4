import type { Address, Hex } from "viem";
import { ZERO_HASH } from "./constants.js";
import { applyBuy, EMPTY_THRONE } from "./rules.js";
import type { CrownEvent, ThroneState } from "./types.js";
import type { BackfillRange, CrownEventSource, CrownSourceLog } from "./store.js";

export interface MockBuy {
  buyer: Address;
  amountEth: bigint;
  now: number;
  txHash?: Hex;
}

export interface MockSell {
  seller: Address;
  amountEth: bigint;
  now: number;
}

export type MockTimelineStep =
  | ({ type: "buy" } & MockBuy)
  | ({ type: "sell" } & MockSell);

export interface MockSourceOptions {
  initialState?: ThroneState;
  autoAbdicateOnSell?: boolean;
  startingBlock?: bigint;
}

export class MockEventSource implements CrownEventSource {
  private readonly listeners = new Set<(log: CrownSourceLog) => void>();
  private logs: CrownSourceLog[] = [];
  private state: ThroneState;
  private nextBlock: bigint;

  constructor(private readonly options: MockSourceOptions = {}) {
    this.state = options.initialState ?? { ...EMPTY_THRONE };
    this.nextBlock = options.startingBlock ?? 1n;
  }

  async getLogs(range?: BackfillRange): Promise<CrownSourceLog[]> {
    return this.logs
      .filter((log) => range?.fromBlock === undefined || log.blockNumber >= range.fromBlock)
      .filter((log) => range?.toBlock === undefined || log.blockNumber <= range.toBlock)
      .map(cloneSourceLog);
  }

  subscribe(onLog: (log: CrownSourceLog) => void): () => void {
    this.listeners.add(onLog);
    return () => {
      this.listeners.delete(onLog);
    };
  }

  emitBuy(buy: MockBuy): CrownSourceLog[] {
    const txHash = buy.txHash ?? syntheticHash(this.logs.length + 1);
    const result = applyBuy(this.state, { ...buy, txHash });
    this.state = result.state;
    return this.appendEvents(result.events);
  }

  emitClaim(king: Address, amountEth: bigint, now: number, txHash?: Hex): CrownSourceLog[] {
    const event: CrownEvent = {
      type: "claimed",
      king,
      amountEth,
      timestamp: Math.trunc(now),
      txHash: txHash ?? syntheticHash(this.logs.length + 1),
    };

    if (this.state.king.toLowerCase() === king.toLowerCase()) {
      this.state = {
        ...this.state,
        pendingPayout:
          this.state.pendingPayout > amountEth ? this.state.pendingPayout - amountEth : 0n,
      };
    }

    return this.appendEvents([event]);
  }

  emitSell(_sell: MockSell): CrownSourceLog[] {
    if (!this.options.autoAbdicateOnSell) {
      return [];
    }

    throw new Error("autoAbdicateOnSell is intentionally unsupported by the default mock");
  }

  runTimeline(timeline: MockTimelineStep[]): CrownSourceLog[] {
    const emitted: CrownSourceLog[] = [];
    for (const step of timeline) {
      if (step.type === "buy") {
        emitted.push(...this.emitBuy(step));
      } else {
        emitted.push(...this.emitSell(step));
      }
    }

    return emitted;
  }

  removeLastBlock(): CrownSourceLog[] {
    if (this.logs.length === 0) {
      return [];
    }

    const blockNumber = this.logs.at(-1)?.blockNumber;
    const removed = this.logs
      .filter((log) => log.blockNumber === blockNumber)
      .map((log) => ({ ...cloneSourceLog(log), removed: true }));

    this.logs = this.logs.filter((log) => log.blockNumber !== blockNumber);
    this.rebuildStateFromLogs();
    for (const log of removed) {
      this.notify(log);
    }

    return removed;
  }

  snapshotState(): ThroneState {
    return { ...this.state };
  }

  private appendEvents(events: CrownEvent[]): CrownSourceLog[] {
    const blockNumber = this.nextBlock;
    this.nextBlock += 1n;
    const logs = events.map((event, index) => ({
      blockNumber,
      logIndex: index,
      event,
    }));

    this.logs.push(...logs);
    for (const log of logs) {
      this.notify(log);
    }

    return logs.map(cloneSourceLog);
  }

  private notify(log: CrownSourceLog): void {
    const cloned = cloneSourceLog(log);
    for (const listener of this.listeners) {
      listener(cloned);
    }
  }

  private rebuildStateFromLogs(): void {
    this.state = { ...EMPTY_THRONE };
    for (const log of this.logs) {
      if (log.event.type === "buy") {
        continue;
      }

      if (log.event.type === "crowned") {
        this.state = {
          king: log.event.king,
          record: log.event.amountEth,
          crownedAt: log.event.timestamp,
          pendingPayout: 0n,
        };
      }

      if (
        log.event.type === "tribute" &&
        this.state.king.toLowerCase() === log.event.king.toLowerCase()
      ) {
        this.state.pendingPayout += log.event.amountEth;
      }

      if (
        log.event.type === "claimed" &&
        this.state.king.toLowerCase() === log.event.king.toLowerCase()
      ) {
        this.state.pendingPayout =
          this.state.pendingPayout > log.event.amountEth
            ? this.state.pendingPayout - log.event.amountEth
            : 0n;
      }
    }
  }
}

function cloneSourceLog(log: CrownSourceLog): CrownSourceLog {
  return {
    ...log,
    event: { ...log.event },
  };
}

function syntheticHash(seed: number): Hex {
  if (seed <= 0) {
    return ZERO_HASH;
  }

  return `0x${seed.toString(16).padStart(64, "0")}` as Hex;
}
