export const BASE_FEE_BPS = 100;
export const CROWN_TAX_BPS = 200;
export const HALF_LIFE = 3_600;
export const MIN_BUY_ETH = 10_000_000_000_000_000n;
export const BPS_DENOMINATOR = 10_000n;

export const ZERO_ADDRESS = "0x0000000000000000000000000000000000000000" as const;
export const ZERO_HASH =
  "0x0000000000000000000000000000000000000000000000000000000000000000" as const;

export interface GameConfig {
  baseFeeBps: number;
  crownTaxBps: number;
  halfLife: number;
  minBuyEth: bigint;
}

export const DEFAULT_CONFIG: GameConfig = {
  baseFeeBps: BASE_FEE_BPS,
  crownTaxBps: CROWN_TAX_BPS,
  halfLife: HALF_LIFE,
  minBuyEth: MIN_BUY_ETH,
};
