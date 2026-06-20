import { describe, expect, it } from "vitest";
import {
  DEFAULT_CONFIG,
  DEFAULT_SIMULATION_BUYS,
  formatSweepTable,
  handWorkedExample,
  runSimulation,
  sweepConfigs,
  washTradeBreakevenVolume,
} from "../src/index.js";

describe("simulator", () => {
  it("reproduces the documented hand-worked default example", () => {
    const metrics = runSimulation(DEFAULT_SIMULATION_BUYS, DEFAULT_CONFIG);

    expect(metrics.crowns).toBe(4);
    expect(metrics.totalTribute).toBe(9_400_000_000_000_000n);
    expect(metrics.washTradeBreakevenVolume).toBe(
      washTradeBreakevenVolume(1_000_000_000_000_000_000n, DEFAULT_CONFIG),
    );
    expect(handWorkedExample()).toContain("washTradeBreakevenVolume=2 ETH");
  });

  it("prints a sweep table with breakeven and dead-throne columns", () => {
    const table = formatSweepTable(
      sweepConfigs({
        buys: DEFAULT_SIMULATION_BUYS,
        halfLives: [DEFAULT_CONFIG.halfLife],
        crownTaxBps: [DEFAULT_CONFIG.crownTaxBps],
        minBuyEth: [DEFAULT_CONFIG.minBuyEth],
      }),
    );

    expect(table).toContain("breakevenVolumeEth");
    expect(table).toContain("deadThrone");
    expect(table).toContain("3600");
  });
});
