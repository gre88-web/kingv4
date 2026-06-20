import {
  decodeEventLog,
  parseAbi,
  type Address,
  type Hex,
  type PublicClient,
} from "viem";
import { ZERO_ADDRESS } from "./constants.js";
import { addressesEqual, effectiveRecord, thresholdToDethrone } from "./rules.js";
import type { CrownEvent, DerivedState, ReignRecord, ThroneState } from "./types.js";

export interface CrownSourceLog {
  blockNumber: bigint;
  logIndex: number;
  event: CrownEvent;
  removed?: boolean;
}

export interface BackfillRange {
  fromBlock?: bigint;
  toBlock?: bigint;
}

export interface CrownEventSource {
  getLogs(range?: BackfillRange): Promise<CrownSourceLog[]>;
  subscribe(onLog: (log: CrownSourceLog) => void): () => void;
}

export const KOTC_HOOK_ABI = parseAbi([
  "event Crowned(address indexed newKing,address indexed dethroned,uint128 buyAmountEth,uint128 newRecord,uint64 timestamp)",
  "event TributePaid(address indexed king,uint128 amountEth,uint128 pendingTotal,uint64 timestamp)",
  "event Claimed(address indexed king,uint128 amountEth,uint64 timestamp)",
  "event BuyRecorded(address indexed buyer,uint128 buyAmountEth,uint128 effectiveRecord,bool dethroned,uint64 timestamp)",
]);

type Listener = () => void;

interface FoldedState {
  throne: ThroneState;
  leaderboard: ReignRecord[];
  pendingByAddress: Map<Address, bigint>;
}

const initialFoldedState = (): FoldedState => ({
  throne: {
    king: ZERO_ADDRESS,
    record: 0n,
    crownedAt: 0,
    pendingPayout: 0n,
  },
  leaderboard: [],
  pendingByAddress: new Map(),
});

export class ThroneStore {
  private readonly logs = new Map<string, CrownSourceLog>();
  private readonly listeners = new Set<Listener>();
  private folded = initialFoldedState();
  private unsubscribeSource?: () => void;
  private lastSeenBlock: bigint | null = null;

  constructor(private readonly source: CrownEventSource) {}

  async start(range?: BackfillRange): Promise<void> {
    await this.backfill(range);
    this.unsubscribeSource = this.source.subscribe((log) => {
      this.ingest(log);
    });
  }

  stop(): void {
    this.unsubscribeSource?.();
    this.unsubscribeSource = undefined;
  }

  async backfill(range?: BackfillRange): Promise<void> {
    const logs = await this.source.getLogs(range);
    this.ingestMany(logs);
  }

  async reconnect(): Promise<void> {
    const fromBlock =
      this.lastSeenBlock === null ? undefined : this.lastSeenBlock + 1n;
    await this.backfill({ fromBlock });
  }

  ingestMany(logs: CrownSourceLog[]): void {
    for (const log of logs) {
      this.applyLogMutation(log);
    }

    this.rebuild();
    this.emit();
  }

  ingest(log: CrownSourceLog): void {
    this.applyLogMutation(log);
    this.rebuild();
    this.emit();
  }

  getSnapshot(): { throne: ThroneState; leaderboard: ReignRecord[] } {
    return {
      throne: { ...this.folded.throne },
      leaderboard: this.folded.leaderboard.map((reign) => ({ ...reign })),
    };
  }

  getDerivedState(now: number, viewer?: Address): DerivedState {
    const throne = { ...this.folded.throne };
    const currentEffectiveRecord = effectiveRecord(throne, now);
    const viewerPending = viewer
      ? this.folded.pendingByAddress.get(canonicalAddress(viewer)) ?? 0n
      : 0n;

    return {
      throne,
      effectiveRecord: currentEffectiveRecord,
      thresholdToDethrone: thresholdToDethrone(throne, now),
      reignDuration:
        throne.king === ZERO_ADDRESS ? 0 : Math.max(0, Math.trunc(now) - throne.crownedAt),
      isViewerKing:
        viewer !== undefined && throne.king !== ZERO_ADDRESS
          ? addressesEqual(viewer, throne.king)
          : false,
      viewerPending,
      leaderboard: this.folded.leaderboard.map((reign) => ({ ...reign })),
    };
  }

  subscribe(listener: Listener): () => void {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }

  private applyLogMutation(log: CrownSourceLog): void {
    const key = logKey(log);
    if (log.removed) {
      this.logs.delete(key);
      return;
    }

    this.logs.set(key, log);
    if (this.lastSeenBlock === null || log.blockNumber > this.lastSeenBlock) {
      this.lastSeenBlock = log.blockNumber;
    }
  }

  private rebuild(): void {
    const logs = [...this.logs.values()].sort(compareLogs);
    const folded = initialFoldedState();

    for (const log of logs) {
      foldEvent(folded, log.event);
    }

    this.folded = folded;
  }

  private emit(): void {
    for (const listener of this.listeners) {
      listener();
    }
  }
}

export function foldEvents(logs: CrownSourceLog[]): {
  throne: ThroneState;
  leaderboard: ReignRecord[];
  pendingByAddress: Map<Address, bigint>;
} {
  const folded = initialFoldedState();
  for (const log of [...logs].sort(compareLogs)) {
    if (!log.removed) {
      foldEvent(folded, log.event);
    }
  }

  return folded;
}

export function createViemEventSource(
  publicClient: PublicClient,
  address: Address,
): CrownEventSource {
  return {
    async getLogs(range?: BackfillRange): Promise<CrownSourceLog[]> {
      const logs = await (publicClient as any).getContractEvents({
        address,
        abi: KOTC_HOOK_ABI,
        fromBlock: range?.fromBlock,
        toBlock: range?.toBlock,
      });

      return logs.map(normalizeViemLog).filter((log: CrownSourceLog | null) => log !== null);
    },
    subscribe(onLog: (log: CrownSourceLog) => void): () => void {
      return (publicClient as any).watchContractEvent({
        address,
        abi: KOTC_HOOK_ABI,
        onLogs(logs: unknown[]) {
          for (const log of logs) {
            const normalized = normalizeViemLog(log);
            if (normalized) {
              onLog(normalized);
            }
          }
        },
      });
    },
  };
}

function foldEvent(folded: FoldedState, event: CrownEvent): void {
  switch (event.type) {
    case "tribute": {
      const king = canonicalAddress(event.king);
      const pending = (folded.pendingByAddress.get(king) ?? 0n) + event.amountEth;
      folded.pendingByAddress.set(king, pending);

      const currentReign = folded.leaderboard.at(-1);
      if (
        currentReign &&
        currentReign.dethronedAt === null &&
        addressesEqual(currentReign.king, king)
      ) {
        currentReign.tributeEarned += event.amountEth;
      }

      if (addressesEqual(folded.throne.king, king)) {
        folded.throne.pendingPayout = pending;
      }
      break;
    }
    case "claimed": {
      const king = canonicalAddress(event.king);
      const pending = folded.pendingByAddress.get(king) ?? 0n;
      const nextPending = pending > event.amountEth ? pending - event.amountEth : 0n;
      folded.pendingByAddress.set(king, nextPending);

      if (addressesEqual(folded.throne.king, king)) {
        folded.throne.pendingPayout = nextPending;
      }
      break;
    }
    case "crowned": {
      const activeReign = folded.leaderboard.at(-1);
      if (activeReign && activeReign.dethronedAt === null) {
        activeReign.dethronedAt = event.timestamp;
      }

      const king = canonicalAddress(event.king);
      const pending = folded.pendingByAddress.get(king) ?? 0n;
      folded.throne = {
        king,
        record: event.amountEth,
        crownedAt: event.timestamp,
        pendingPayout: pending,
      };
      folded.leaderboard.push({
        king,
        record: event.amountEth,
        crownedAt: event.timestamp,
        dethronedAt: null,
        tributeEarned: 0n,
      });
      break;
    }
    case "buy":
      break;
    default:
      assertNever(event);
  }
}

function normalizeViemLog(log: any): CrownSourceLog | null {
  const blockNumber = BigInt(log.blockNumber ?? 0n);
  const logIndex = Number(log.logIndex ?? 0);
  const txHash = (log.transactionHash ?? log.txHash) as Hex;
  const eventName = log.eventName ?? tryDecodeEventName(log);
  const args = log.args ?? tryDecodeArgs(log);

  if (!eventName || !args || !txHash) {
    return null;
  }

  const removed = Boolean(log.removed);
  const event = normalizeDecodedEvent(eventName, args, txHash);
  if (!event) {
    return null;
  }

  return { blockNumber, logIndex, event, removed };
}

function tryDecodeEventName(log: any): string | undefined {
  try {
    return decodeEventLog({
      abi: KOTC_HOOK_ABI,
      data: log.data,
      topics: log.topics,
    }).eventName;
  } catch {
    return undefined;
  }
}

function tryDecodeArgs(log: any): unknown {
  try {
    return decodeEventLog({
      abi: KOTC_HOOK_ABI,
      data: log.data,
      topics: log.topics,
    }).args;
  } catch {
    return undefined;
  }
}

function normalizeDecodedEvent(
  eventName: string,
  args: any,
  txHash: Hex,
): CrownEvent | null {
  switch (eventName) {
    case "Crowned":
      return {
        type: "crowned",
        king: canonicalAddress(args.newKing),
        dethroned: canonicalAddress(args.dethroned),
        amountEth: BigInt(args.buyAmountEth),
        timestamp: Number(args.timestamp),
        txHash,
      };
    case "TributePaid":
      return {
        type: "tribute",
        king: canonicalAddress(args.king),
        amountEth: BigInt(args.amountEth),
        timestamp: Number(args.timestamp),
        txHash,
      };
    case "Claimed":
      return {
        type: "claimed",
        king: canonicalAddress(args.king),
        amountEth: BigInt(args.amountEth),
        timestamp: Number(args.timestamp),
        txHash,
      };
    case "BuyRecorded":
      return {
        type: "buy",
        king: canonicalAddress(args.buyer),
        amountEth: BigInt(args.buyAmountEth),
        effectiveRecord: BigInt(args.effectiveRecord),
        timestamp: Number(args.timestamp),
        txHash,
      };
    default:
      return null;
  }
}

function compareLogs(left: CrownSourceLog, right: CrownSourceLog): number {
  if (left.blockNumber === right.blockNumber) {
    return left.logIndex - right.logIndex;
  }

  return left.blockNumber < right.blockNumber ? -1 : 1;
}

function logKey(log: CrownSourceLog): string {
  return `${log.blockNumber.toString()}:${log.logIndex}:${log.event.txHash}`;
}

function canonicalAddress(address: Address): Address {
  return address.toLowerCase() as Address;
}

function assertNever(value: never): never {
  throw new Error(`Unexpected event: ${JSON.stringify(value)}`);
}
