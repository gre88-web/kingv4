import { describe, expect, it } from "vitest";
import decayFixture from "../../../docs/fixtures/decay.json";
import {
  CROWN_TAX_BPS,
  EMPTY_THRONE,
  MIN_BUY_ETH,
  applyBuy,
  effectiveRecord,
  thresholdToDethrone,
  tributeFor,
} from "../src/index.js";
import type { ThroneState } from "../src/index.js";

const alice = "0x1000000000000000000000000000000000000001" as const;
const bob = "0x2000000000000000000000000000000000000002" as const;
const carol = "0x3000000000000000000000000000000000000003" as const;

describe("rules", () => {
  it("matches the canonical decay fixture", () => {
    for (const fixture of decayFixture.cases) {
      const state: ThroneState = {
        king: alice,
        record: BigInt(fixture.record),
        crownedAt: 1_000,
        pendingPayout: 0n,
      };

      expect(effectiveRecord(state, 1_000 + fixture.elapsed)).toBe(
        BigInt(fixture.effective),
      );
      expect(thresholdToDethrone(state, 1_000 + fixture.elapsed)).toBe(
        BigInt(fixture.effective),
      );
    }
  });

  it("computes tribute from crown tax basis points", () => {
    expect(tributeFor(1_000_000_000_000_000_000n)).toBe(
      (1_000_000_000_000_000_000n * BigInt(CROWN_TAX_BPS)) / 10_000n,
    );
  });

  it("applies buys with tribute before strict dethroning", () => {
    const first = applyBuy(EMPTY_THRONE, {
      buyer: alice,
      amountEth: 100_000_000_000_000_000n,
      now: 0,
    });

    expect(first.state).toEqual({
      king: alice,
      record: 100_000_000_000_000_000n,
      crownedAt: 0,
      pendingPayout: 0n,
    });
    expect(first.events.map((event) => event.type)).toEqual(["crowned", "buy"]);

    const tieAfterDecay = applyBuy(first.state, {
      buyer: bob,
      amountEth: 75_000_000_000_000_000n,
      now: 1_800,
    });

    expect(tieAfterDecay.state.king).toBe(alice);
    expect(tieAfterDecay.state.pendingPayout).toBe(1_500_000_000_000_000n);
    expect(tieAfterDecay.events.map((event) => event.type)).toEqual([
      "tribute",
      "buy",
    ]);
    expect(tieAfterDecay.events.at(-1)?.effectiveRecord).toBe(
      75_000_000_000_000_000n,
    );

    const dethrone = applyBuy(tieAfterDecay.state, {
      buyer: carol,
      amountEth: 75_000_000_000_000_001n,
      now: 1_800,
    });

    expect(dethrone.state).toEqual({
      king: carol,
      record: 75_000_000_000_000_001n,
      crownedAt: 1_800,
      pendingPayout: 0n,
    });
    expect(dethrone.events.map((event) => event.type)).toEqual([
      "tribute",
      "crowned",
      "buy",
    ]);
    expect(dethrone.events[1]).toMatchObject({
      type: "crowned",
      king: carol,
      dethroned: alice,
      amountEth: 75_000_000_000_000_001n,
    });
  });

  it("does not crown dust even when it exceeds an empty record", () => {
    const result = applyBuy(EMPTY_THRONE, {
      buyer: alice,
      amountEth: MIN_BUY_ETH - 1n,
      now: 0,
    });

    expect(result.state.king).toBe(EMPTY_THRONE.king);
    expect(result.events.map((event) => event.type)).toEqual(["buy"]);
  });
});
