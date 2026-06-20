import type { Address, Hex } from "viem";
import {
  BPS_DENOMINATOR,
  CROWN_TAX_BPS,
  DEFAULT_CONFIG,
  ZERO_ADDRESS,
  ZERO_HASH,
  type GameConfig,
} from "./constants.js";
import type { CrownEvent, ThroneState } from "./types.js";

export interface BuyInput {
  buyer: Address;
  amountEth: bigint;
  now: number;
  txHash?: Hex;
}

export interface ApplyBuyResult {
  state: ThroneState;
  events: CrownEvent[];
}

export const EMPTY_THRONE: ThroneState = {
  king: ZERO_ADDRESS,
  record: 0n,
  crownedAt: 0,
  pendingPayout: 0n,
};

/** Decayed record at time `now`. MUST match the on-chain approximation + fixtures. */
export function effectiveRecord(state: ThroneState, now: number): bigint {
  return effectiveRecordWithConfig(state, now, DEFAULT_CONFIG);
}

export function effectiveRecordWithConfig(
  state: ThroneState,
  now: number,
  config: Pick<GameConfig, "halfLife">,
): bigint {
  if (state.record <= 0n) {
    return 0n;
  }

  const elapsed = Math.max(0, Math.trunc(now) - Math.trunc(state.crownedAt));
  if (elapsed === 0) {
    return state.record;
  }

  if (!Number.isSafeInteger(config.halfLife) || config.halfLife <= 0) {
    throw new Error("halfLife must be a positive safe integer");
  }

  const fullHalfLives = Math.floor(elapsed / config.halfLife);
  if (fullHalfLives >= 256) {
    return 0n;
  }

  const halved = state.record >> BigInt(fullHalfLives);
  const partialElapsed = elapsed % config.halfLife;
  if (partialElapsed === 0 || halved === 0n) {
    return halved;
  }

  // Interpolate linearly from the current half-life boundary to the next halved value.
  return (halved * BigInt(2 * config.halfLife - partialElapsed)) / BigInt(2 * config.halfLife);
}

/** ETH a new buy must STRICTLY exceed to take the crown right now. */
export function thresholdToDethrone(state: ThroneState, now: number): bigint {
  return effectiveRecord(state, now);
}

export function thresholdToDethroneWithConfig(
  state: ThroneState,
  now: number,
  config: Pick<GameConfig, "halfLife">,
): bigint {
  return effectiveRecordWithConfig(state, now, config);
}

/** Tribute skimmed from a single buy = amountEth * CROWN_TAX_BPS / 10_000. */
export function tributeFor(amountEth: bigint): bigint {
  return tributeForWithConfig(amountEth, { crownTaxBps: CROWN_TAX_BPS });
}

export function tributeForWithConfig(
  amountEth: bigint,
  config: Pick<GameConfig, "crownTaxBps">,
): bigint {
  if (amountEth < 0n) {
    throw new Error("amountEth must be non-negative");
  }

  return (amountEth * BigInt(config.crownTaxBps)) / BPS_DENOMINATOR;
}

/** Apply a buy to throne state. Returns the next state + the events it would emit.
 *  Mirrors the hook's afterSwap exactly:
 *   1. credit tribute to the CURRENT king (pull model) -> TributePaid
 *   2. compute effectiveRecord(now)
 *   3. if buyEth > effectiveRecord && buyEth >= MIN_BUY_ETH -> dethrone -> Crowned
 *      (old king keeps already-accrued pending)
 *   4. always -> BuyRecorded
 */
export function applyBuy(state: ThroneState, buy: BuyInput): ApplyBuyResult {
  return applyBuyWithConfig(state, buy, DEFAULT_CONFIG);
}

export function applyBuyWithConfig(
  state: ThroneState,
  buy: BuyInput,
  config: GameConfig,
): ApplyBuyResult {
  if (buy.amountEth < 0n) {
    throw new Error("buy amountEth must be non-negative");
  }

  const now = Math.trunc(buy.now);
  const txHash = buy.txHash ?? ZERO_HASH;
  const currentKing = state.king;
  const hasKing = currentKing !== ZERO_ADDRESS;
  const buyerIsCurrentKing = addressesEqual(buy.buyer, currentKing);
  const events: CrownEvent[] = [];
  let pendingPayout = state.pendingPayout;

  if (hasKing && !buyerIsCurrentKing) {
    const tribute = tributeForWithConfig(buy.amountEth, config);
    if (tribute > 0n) {
      pendingPayout += tribute;
      events.push({
        type: "tribute",
        king: currentKing,
        amountEth: tribute,
        timestamp: now,
        txHash,
      });
    }
  }

  const threshold = effectiveRecordWithConfig(state, now, config);
  const crowned = buy.amountEth > threshold && buy.amountEth >= config.minBuyEth;
  let nextState: ThroneState = {
    ...state,
    pendingPayout,
  };

  if (crowned) {
    const dethroned =
      hasKing && !buyerIsCurrentKing ? currentKing : ZERO_ADDRESS;

    nextState = {
      king: buy.buyer,
      record: buy.amountEth,
      crownedAt: now,
      pendingPayout: buyerIsCurrentKing ? pendingPayout : 0n,
    };

    events.push({
      type: "crowned",
      king: buy.buyer,
      dethroned,
      amountEth: buy.amountEth,
      timestamp: now,
      txHash,
    });
  }

  events.push({
    type: "buy",
    king: buy.buyer,
    amountEth: buy.amountEth,
    effectiveRecord: threshold,
    timestamp: now,
    txHash,
  });

  return { state: nextState, events };
}

export function addressesEqual(left: Address, right: Address): boolean {
  return left.toLowerCase() === right.toLowerCase();
}
