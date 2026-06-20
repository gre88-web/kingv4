import { describe, expect, it } from "vitest";
import {
  MockEventSource,
  ThroneStore,
  tributeFor,
} from "../src/index.js";

const alice = "0x1000000000000000000000000000000000000001" as const;
const bob = "0x2000000000000000000000000000000000000002" as const;
const carol = "0x3000000000000000000000000000000000000003" as const;
const dave = "0x4000000000000000000000000000000000000004" as const;

describe("ThroneStore", () => {
  it("rebuilds derived state from backfilled logs and live reconnects", async () => {
    const source = new MockEventSource();
    source.emitBuy({
      buyer: alice,
      amountEth: 100_000_000_000_000_000n,
      now: 0,
    });
    source.emitBuy({
      buyer: bob,
      amountEth: 80_000_000_000_000_000n,
      now: 900,
    });

    const store = new ThroneStore(source);
    await store.start();

    const backfilled = store.getDerivedState(900, alice);
    expect(backfilled.throne.king).toBe(alice);
    expect(backfilled.viewerPending).toBe(tributeFor(80_000_000_000_000_000n));
    expect(backfilled.leaderboard).toHaveLength(1);

    source.emitBuy({
      buyer: carol,
      amountEth: 120_000_000_000_000_000n,
      now: 1_800,
    });

    const live = store.getDerivedState(1_800, alice);
    expect(live.throne.king).toBe(carol);
    expect(live.throne.pendingPayout).toBe(0n);
    expect(live.viewerPending).toBe(
      tributeFor(80_000_000_000_000_000n) +
        tributeFor(120_000_000_000_000_000n),
    );
    expect(live.leaderboard).toEqual([
      {
        king: alice,
        record: 100_000_000_000_000_000n,
        crownedAt: 0,
        dethronedAt: 1_800,
        tributeEarned:
          tributeFor(80_000_000_000_000_000n) +
          tributeFor(120_000_000_000_000_000n),
      },
      {
        king: carol,
        record: 120_000_000_000_000_000n,
        crownedAt: 1_800,
        dethronedAt: null,
        tributeEarned: 0n,
      },
    ]);

    source.emitClaim(alice, tributeFor(80_000_000_000_000_000n), 2_000);
    const afterClaim = store.getDerivedState(2_000, alice);
    expect(afterClaim.viewerPending).toBe(tributeFor(120_000_000_000_000_000n));

    source.emitBuy({
      buyer: dave,
      amountEth: 90_000_000_000_000_000n,
      now: 3_600,
    });
    await store.reconnect();

    const afterReconnect = store.getDerivedState(3_600, carol);
    expect(afterReconnect.throne.king).toBe(carol);
    expect(afterReconnect.viewerPending).toBe(tributeFor(90_000_000_000_000_000n));
  });

  it("reconciles a reorg that removes the last crowning block", async () => {
    const source = new MockEventSource();
    source.emitBuy({
      buyer: alice,
      amountEth: 100_000_000_000_000_000n,
      now: 0,
    });
    source.emitBuy({
      buyer: bob,
      amountEth: 80_000_000_000_000_000n,
      now: 900,
    });

    const store = new ThroneStore(source);
    await store.start();

    source.emitBuy({
      buyer: carol,
      amountEth: 120_000_000_000_000_000n,
      now: 1_800,
    });
    expect(store.getDerivedState(1_800).throne.king).toBe(carol);

    source.removeLastBlock();

    const reverted = store.getDerivedState(1_800, alice);
    expect(reverted.throne.king).toBe(alice);
    expect(reverted.viewerPending).toBe(tributeFor(80_000_000_000_000_000n));
    expect(reverted.leaderboard).toEqual([
      {
        king: alice,
        record: 100_000_000_000_000_000n,
        crownedAt: 0,
        dethronedAt: null,
        tributeEarned: tributeFor(80_000_000_000_000_000n),
      },
    ]);
  });
});
