from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

# Source kinds. Correlation counts how many *distinct kinds* point at the same token,
# because two signals from the same kind (e.g. two exchanges) are less independent
# than a code change plus a wallet flow.
CODE = "code"
EXCHANGE = "exchange"
ONCHAIN = "onchain"


@dataclass
class Signal:
    source: str                 # watcher name, e.g. "bitgo-statics", "coinbase", "onchain:base"
    kind: str                   # CODE | EXCHANGE | ONCHAIN
    title: str                  # one-line human summary
    weight: float               # how much this signal alone should count
    chain: str | None = None    # ethereum | base | robinhood | ink | None
    symbol: str | None = None   # upper-case ticker if known
    address: str | None = None  # lower-case token contract address if known
    detail: dict[str, Any] = field(default_factory=dict)
    ts: float = field(default_factory=time.time)
    id: int | None = None

    def __post_init__(self) -> None:
        if self.symbol:
            self.symbol = self.symbol.strip().upper()
        if self.address:
            self.address = self.address.strip().lower()
