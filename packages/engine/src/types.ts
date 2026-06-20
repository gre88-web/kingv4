import type { Address, Hex } from "viem";

/** Mirrors the on-chain Throne struct. */
export interface ThroneState {
  king: Address;
  record: bigint;
  crownedAt: number;
  pendingPayout: bigint;
}

/** One historical reign, for the leaderboard. */
export interface ReignRecord {
  king: Address;
  record: bigint;
  crownedAt: number;
  dethronedAt: number | null;
  tributeEarned: bigint;
}

/** A normalized event from the chain. */
export interface CrownEvent {
  type: "crowned" | "tribute" | "claimed" | "buy";
  king: Address;
  dethroned?: Address;
  amountEth: bigint;
  effectiveRecord?: bigint;
  timestamp: number;
  txHash: Hex;
}

/** What the UI binds to - derived from ThroneState + history at `now`. */
export interface DerivedState {
  throne: ThroneState;
  effectiveRecord: bigint;
  thresholdToDethrone: bigint;
  reignDuration: number;
  isViewerKing: boolean;
  viewerPending: bigint;
  leaderboard: ReignRecord[];
}
