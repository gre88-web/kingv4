import type { Address } from "viem";
import {
  BPS_DENOMINATOR,
  DEFAULT_CONFIG,
  type GameConfig,
} from "./constants.js";
import {
  applyBuyWithConfig,
  EMPTY_THRONE,
  tributeForWithConfig,
} from "./rules.js";
import type { CrownEvent, ThroneState } from "./types.js";

export interface SimulatedBuy {
  buyer: Address;
  amountEth: bigint;
  at: number;
}

export interface SimulationMetrics {
  config: GameConfig;
  crowns: number;
  averageReignLength: number;
  flipsPerHour: number;
  totalTribute: bigint;
  averageKingRoiBps: number;
  washTradeBreakevenVolume: bigint;
  deadThrone: boolean;
}

export interface SweepInput {
  buys: SimulatedBuy[];
  halfLives?: number[];
  crownTaxBps?: number[];
  minBuyEth?: bigint[];
}

export const DEFAULT_SIMULATION_BUYS: SimulatedBuy[] = [
  {
    buyer: "0x1000000000000000000000000000000000000001",
    amountEth: 100_000_000_000_000_000n,
    at: 0,
  },
  {
    buyer: "0x2000000000000000000000000000000000000002",
    amountEth: 80_000_000_000_000_000n,
    at: 900,
  },
  {
    buyer: "0x3000000000000000000000000000000000000003",
    amountEth: 120_000_000_000_000_000n,
    at: 1_800,
  },
  {
    buyer: "0x4000000000000000000000000000000000000004",
    amountEth: 70_000_000_000_000_000n,
    at: 5_400,
  },
  {
    buyer: "0x5000000000000000000000000000000000000005",
    amountEth: 200_000_000_000_000_000n,
    at: 7_200,
  },
];

export function runSimulation(
  buys: SimulatedBuy[],
  config: GameConfig = DEFAULT_CONFIG,
): SimulationMetrics {
  const orderedBuys = [...buys].sort((left, right) => left.at - right.at);
  let state: ThroneState = { ...EMPTY_THRONE };
  const crownedEvents: CrownEvent[] = [];
  const tributeByKing = new Map<Address, bigint>();
  let totalTribute = 0n;

  for (const buy of orderedBuys) {
    const result = applyBuyWithConfig(
      state,
      { buyer: buy.buyer, amountEth: buy.amountEth, now: buy.at },
      config,
    );
    state = result.state;

    for (const event of result.events) {
      if (event.type === "crowned") {
        crownedEvents.push(event);
      }

      if (event.type === "tribute") {
        totalTribute += event.amountEth;
        tributeByKing.set(event.king, (tributeByKing.get(event.king) ?? 0n) + event.amountEth);
      }
    }
  }

  const elapsed =
    orderedBuys.length <= 1
      ? 0
      : orderedBuys.at(-1)!.at - orderedBuys[0]!.at;
  const reignLengths = crownedEvents.map((event, index) => {
    const next = crownedEvents[index + 1];
    return (next?.timestamp ?? orderedBuys.at(-1)?.at ?? event.timestamp) - event.timestamp;
  });
  const averageReignLength =
    reignLengths.length === 0
      ? 0
      : reignLengths.reduce((sum, length) => sum + length, 0) / reignLengths.length;
  const flipsPerHour = elapsed <= 0 ? 0 : (crownedEvents.length / elapsed) * 3_600;
  const averageKingRoiBps = averageRoiBps(crownedEvents, tributeByKing);

  return {
    config,
    crowns: crownedEvents.length,
    averageReignLength,
    flipsPerHour,
    totalTribute,
    averageKingRoiBps,
    washTradeBreakevenVolume: washTradeBreakevenVolume(1_000_000_000_000_000_000n, config),
    deadThrone: detectDeadThrone(crownedEvents, orderedBuys, config),
  };
}

export function sweepConfigs(input: SweepInput): SimulationMetrics[] {
  const halfLives = input.halfLives ?? [1_800, DEFAULT_CONFIG.halfLife, 7_200];
  const crownTaxBps = input.crownTaxBps ?? [100, DEFAULT_CONFIG.crownTaxBps, 400];
  const minBuyEth = input.minBuyEth ?? [5_000_000_000_000_000n, DEFAULT_CONFIG.minBuyEth];
  const metrics: SimulationMetrics[] = [];

  for (const halfLife of halfLives) {
    for (const taxBps of crownTaxBps) {
      for (const minBuy of minBuyEth) {
        metrics.push(
          runSimulation(input.buys, {
            baseFeeBps: DEFAULT_CONFIG.baseFeeBps,
            crownTaxBps: taxBps,
            halfLife,
            minBuyEth: minBuy,
          }),
        );
      }
    }
  }

  return metrics;
}

export function formatSweepTable(metrics: SimulationMetrics[]): string {
  const rows = [
    [
      "halfLife",
      "taxBps",
      "minBuyEth",
      "crowns",
      "avgReignSec",
      "flipsPerHour",
      "avgRoiBps",
      "breakevenVolumeEth",
      "deadThrone",
    ],
    ...metrics.map((metric) => [
      metric.config.halfLife.toString(),
      metric.config.crownTaxBps.toString(),
      formatEth(metric.config.minBuyEth),
      metric.crowns.toString(),
      metric.averageReignLength.toFixed(0),
      metric.flipsPerHour.toFixed(2),
      metric.averageKingRoiBps.toFixed(2),
      formatEth(metric.washTradeBreakevenVolume),
      metric.deadThrone ? "yes" : "no",
    ]),
  ];

  const widths = rows[0].map((_, index) =>
    Math.max(...rows.map((row) => row[index]!.length)),
  );

  return rows
    .map((row) =>
      row.map((cell, index) => cell.padStart(widths[index]!)).join("  "),
    )
    .join("\n");
}

export function handWorkedExample(): string {
  const metrics = runSimulation(DEFAULT_SIMULATION_BUYS, DEFAULT_CONFIG);
  return [
    "Default constants hand-worked simulation:",
    `crowns=${metrics.crowns}`,
    `averageReignLength=${metrics.averageReignLength.toFixed(0)}s`,
    `flipsPerHour=${metrics.flipsPerHour.toFixed(2)}`,
    `totalTribute=${formatEth(metrics.totalTribute)} ETH`,
    `washTradeBreakevenVolume=${formatEth(metrics.washTradeBreakevenVolume)} ETH`,
  ].join("\n");
}

export function washTradeBreakevenVolume(capitalAtRisk: bigint, config: GameConfig): bigint {
  if (config.crownTaxBps <= 0) {
    return 0n;
  }

  const roundTripBaseFees =
    (capitalAtRisk * BigInt(config.baseFeeBps * 2)) / BPS_DENOMINATOR;
  const entryCrownTax = tributeForWithConfig(capitalAtRisk, config);
  const neededTribute = roundTripBaseFees + entryCrownTax;
  return (neededTribute * BPS_DENOMINATOR) / BigInt(config.crownTaxBps);
}

function averageRoiBps(
  crownedEvents: CrownEvent[],
  tributeByKing: Map<Address, bigint>,
): number {
  if (crownedEvents.length === 0) {
    return 0;
  }

  const roiBps = crownedEvents.map((event) => {
    const tribute = tributeByKing.get(event.king) ?? 0n;
    if (event.amountEth === 0n) {
      return 0;
    }

    return Number((tribute * BPS_DENOMINATOR) / event.amountEth);
  });

  return roiBps.reduce((sum, roi) => sum + roi, 0) / roiBps.length;
}

function detectDeadThrone(
  crownedEvents: CrownEvent[],
  buys: SimulatedBuy[],
  config: GameConfig,
): boolean {
  if (crownedEvents.length === 0 || buys.length === 0) {
    return false;
  }

  const firstRecord = crownedEvents[0]!.amountEth;
  const maxLaterBuy = buys.slice(1).reduce((max, buy) => (buy.amountEth > max ? buy.amountEth : max), 0n);
  return crownedEvents.length === 1 && maxLaterBuy < firstRecord / 2n && config.halfLife > 7_200;
}

function formatEth(wei: bigint): string {
  const whole = wei / 1_000_000_000_000_000_000n;
  const fraction = wei % 1_000_000_000_000_000_000n;
  const fractionText = fraction.toString().padStart(18, "0").replace(/0+$/, "");
  return fractionText.length === 0 ? whole.toString() : `${whole}.${fractionText}`;
}

if (process.argv[1]?.endsWith("simulator.js")) {
  const metrics = sweepConfigs({ buys: DEFAULT_SIMULATION_BUYS });
  console.log(handWorkedExample());
  console.log("");
  console.log(formatSweepTable(metrics));
}
