"""Score each new signal against everything else seen for the same token.

A token is matched by contract address, or by ticker (common tickers like USDC are
ignored because they match everything). The score counts each source once, at its
strongest signal, and adds a bonus for every extra *kind* of source: code + exchange +
onchain agreeing is much stronger than any one of them shouting.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from .models import Signal
from .store import Store

COMMON_SYMBOLS = {"USDC", "USDT", "USDT0", "DAI", "WETH", "ETH", "WBTC", "BTC", "USDG", "USD", "EUR", "EURC",
                  "PYUSD", "CBBTC", "STETH", "WSTETH", "USDE", "FDUSD", "KBTC", "USDS", "RLUSD"}

SEVERITIES = ["low", "medium", "high"]


@dataclass
class Assessment:
    signal: Signal
    related: list[Signal]
    score: float
    kinds: set[str]
    sources: dict[str, float] = field(default_factory=dict)

    @property
    def severity(self) -> str:
        if len(self.kinds) >= 2 and self.score >= 6:
            return "high"
        if self.score >= 4:
            return "medium"
        return "low"

    @property
    def token(self) -> str:
        s = self.signal
        return s.symbol or (s.address[:10] if s.address else "?")


def assess(store: Store, s: Signal, window_days: float = 30.0, kind_bonus: float = 2.0,
           ignore_symbols: set[str] = COMMON_SYMBOLS) -> Assessment:
    rel = store.related(s, since=time.time() - window_days * 86400, ignore_symbols=ignore_symbols)
    best: dict[str, float] = {}
    for r in rel:
        best[r.source] = max(best.get(r.source, 0.0), r.weight)
    kinds = {r.kind for r in rel}
    score = sum(best.values()) + kind_bonus * (len(kinds) - 1)
    return Assessment(signal=s, related=rel, score=round(score, 2), kinds=kinds, sources=best)


def severity_at_least(sev: str, minimum: str) -> bool:
    return SEVERITIES.index(sev) >= SEVERITIES.index(minimum)
