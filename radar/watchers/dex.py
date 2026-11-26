"""Alert when a DEX pool is created for a token another source already flagged.

Flagged tokens (from code or exchange signals) go on a per-chain watchlist. Each poll
scans pool-creation events from *any* factory where the token is one side of the pair:

* Uniswap V2-style ``PairCreated``, Uniswap V3-style ``PoolCreated`` (also PancakeSwap and forks)
* Uniswap V4 ``Initialize`` on the PoolManager (also Clanker/Zora-style hooked pools)
* Aerodrome / Velodrome V2 ``PoolCreated`` and Slipstream (CL) ``PoolCreated``

Filtering by token topic instead of factory address means forks and new DEXes are
caught too; known factories just get a friendly name.
"""
from __future__ import annotations

import logging
import time
from typing import Any

from ..correlate import COMMON_SYMBOLS
from ..keccak import topic
from ..models import ONCHAIN, Signal
from ..store import Store
from .base import Watcher
from .onchain import RPC, _addr, _topic, fetch_logs

log = logging.getLogger(__name__)

EVENTS = {
    topic("PairCreated(address,address,address,uint256)"): "v2",
    topic("PoolCreated(address,address,uint24,int24,address)"): "v3",
    topic("Initialize(bytes32,address,address,uint24,int24,address,uint160,int24)"): "v4",
    topic("PoolCreated(address,address,bool,address,uint256)"): "solidly",
    topic("PoolCreated(address,address,int24,address)"): "slipstream",
}
V4 = next(k for k, v in EVENTS.items() if v == "v4")
NON_V4 = [k for k, v in EVENTS.items() if v != "v4"]

# Seen emitting these events on-chain (Nov 2026). Unknown factories are reported by address.
KNOWN_FACTORIES = {
    "ethereum": {
        "0x5c69bee701ef814a2b6a3edd4b1652cb9cc5aa6f": "Uniswap V2",
        "0x1f98431c8ad98523631ae4a59f267346ea31f984": "Uniswap V3",
        "0x000000000004444c5dc75cb358380d2e3de08a90": "Uniswap V4",
        "0x0bfbcf9fa4f9c56b0f40a671ad40e0805a091865": "PancakeSwap V3",
    },
    "base": {
        "0x8909dc15e40173ff4699343b6eb8132c65e18ec6": "Uniswap V2",
        "0x498581ff718922c3f8e6a244956af099b2652b2b": "Uniswap V4",
        "0x420dd381b31aef6683db6b902084cb0ffece40da": "Aerodrome",
        "0x5e7bb104d84c7cb9b682aac2f3d509f5f406809a": "Aerodrome Slipstream",
    },
    "ink": {"0x360e68faccca8ca495c1b759fd9eee466db9fb32": "Uniswap V4"},
    "robinhood": {"0x0bfbcf9fa4f9c56b0f40a671ad40e0805a091865": "PancakeSwap V3"},
}
V4_DYNAMIC_FEE = 0x800000  # LPFeeLibrary.DYNAMIC_FEE_FLAG: the hook sets the fee per swap
STYLE = {"v2": "V2-style", "v3": "V3-style", "v4": "V4-style", "solidly": "Solidly-style", "slipstream": "CL-style"}


def _words(data: str) -> list[str]:
    d = (data or "0x").removeprefix("0x")
    return [d[i:i + 64] for i in range(0, len(d), 64)]


def decode_pool_event(lg: dict[str, Any]) -> dict[str, Any] | None:
    t = lg.get("topics") or []
    kind = EVENTS.get(t[0]) if t else None
    if not kind:
        return None
    w = _words(lg.get("data", "0x"))
    try:
        if kind == "v4":
            return {"kind": kind, "token0": _addr(t[2]), "token1": _addr(t[3]), "pool": t[1],
                    "fee": int(w[0], 16), "hooks": "0x" + w[2][-40:]}
        out = {"kind": kind, "token0": _addr(t[1]), "token1": _addr(t[2])}
        if kind == "v2":
            out["pool"] = "0x" + w[0][-40:]
        elif kind == "v3":
            out.update(pool="0x" + w[1][-40:], fee=int(t[3], 16))
        elif kind == "solidly":
            out.update(pool="0x" + w[0][-40:], stable=bool(int(t[3], 16)))
        else:
            out["pool"] = "0x" + w[0][-40:]
        return out
    except (IndexError, ValueError):
        return None


class DexWatcher(Watcher):
    kind = ONCHAIN

    def __init__(self, chain: str, rpc: RPC, *, max_block_range: int = 1000, confirmations: int = 3,
                 backfill_blocks: int = 5000, watch_days: float = 45, weight: float = 3.0,
                 token_meta=None, interval: float = 60) -> None:
        super().__init__(f"dex:{chain}", interval)
        self.chain, self.rpc = chain, rpc
        self.max_range, self.confirmations = max_block_range, confirmations
        self.backfill, self.watch_days, self.weight = backfill_blocks, watch_days, weight
        self.token_meta = token_meta  # callable(store, address) -> {"symbol", "decimals", ...}

    # ---- watchlist -------------------------------------------------------------
    def watch(self, store: Store, address: str, symbol: str | None = None, reason: str = "") -> bool:
        address = address.lower()
        if symbol and symbol.upper() in COMMON_SYMBOLS:
            return False  # WETH/USDC/... pair with everything; watching them is pure noise
        wl = store.get("watchlist", self.chain, {})
        if address in wl:
            return False
        wl[address] = {"symbol": symbol, "reason": reason, "added": time.time(),
                       "expires": time.time() + self.watch_days * 86400, "backfilled": False}
        store.put("watchlist", self.chain, wl)
        log.info("%s: watching %s %s for new pools", self.name, symbol or "", address)
        return True

    def _active(self, store: Store) -> dict[str, dict[str, Any]]:
        wl = store.get("watchlist", self.chain, {})
        live = {a: v for a, v in wl.items() if v["expires"] > time.time()}
        if len(live) != len(wl):
            store.put("watchlist", self.chain, live)
        return live

    # ---- scanning --------------------------------------------------------------
    def _scan(self, frm: int, to: int, tokens: list[str]) -> list[dict[str, Any]]:
        tt = [_topic(a) for a in tokens]
        seen, out = set(), []
        for topics in ([NON_V4, tt], [list(EVENTS), None, tt], [V4, None, None, tt]):
            for lg in fetch_logs(self.rpc, frm, to, {"topics": topics}, self.max_range):
                key = (lg.get("transactionHash"), lg.get("logIndex"))
                if key not in seen:
                    seen.add(key)
                    out.append(lg)
        return out

    def poll(self, store: Store) -> list[Signal]:
        head = int(self.rpc.call("eth_blockNumber", []), 16) - self.confirmations
        cursor = store.get("dex-cursor", self.chain)
        wl = self._active(store)
        if cursor is None or not wl:
            store.put("dex-cursor", self.chain, head)  # nothing to watch yet: just keep up with the head
            return []

        logs: list[dict[str, Any]] = []
        fresh = [a for a, v in wl.items() if not v["backfilled"]]
        if fresh:  # look back a little for tokens added since the last poll
            logs += self._scan(max(0, cursor - self.backfill), cursor, fresh)
            for a in fresh:
                wl[a]["backfilled"] = True
            store.put("watchlist", self.chain, wl)
        if head > cursor:
            logs += self._scan(cursor + 1, head, list(wl))
        store.put("dex-cursor", self.chain, max(cursor, head))

        signals = []
        for lg in logs:
            ev = decode_pool_event(lg)
            if not ev:
                continue
            if not store.mark_seen(f"pools:{self.chain}", f"{lg['address'].lower()}:{ev['pool']}"):
                continue
            for side, other in (("token0", "token1"), ("token1", "token0")):
                tok = ev[side]
                if tok in wl:
                    signals.append(self._signal(store, lg, ev, tok, ev[other], wl[tok]))
        return signals

    def _meta(self, store: Store, token: str) -> dict[str, Any]:
        return self.token_meta(store, token) if self.token_meta else {}

    def _signal(self, store: Store, lg: dict[str, Any], ev: dict[str, Any], token: str, quote: str,
                entry: dict[str, Any]) -> Signal:
        factory = lg["address"].lower()
        dex = KNOWN_FACTORIES.get(self.chain, {}).get(factory) or f"{STYLE[ev['kind']]} DEX {factory[:10]}"
        tm, qm = self._meta(store, token), self._meta(store, quote)
        sym = tm.get("symbol") or entry.get("symbol") or token[:10]
        qsym = qm.get("symbol") or ("ETH" if quote == "0x" + "0" * 40 else quote[:10])
        liq = self._liquidity(ev, token, quote, tm, qm, sym, qsym)
        extra = []
        if ev.get("fee") is not None and ev["kind"] in ("v3", "v4"):
            extra.append("dynamic fee" if ev["fee"] & V4_DYNAMIC_FEE else f"fee {ev['fee'] / 10000:g}%")
        if ev["kind"] == "v4" and ev.get("hooks") and int(ev["hooks"], 16):
            extra.append(f"hooks {ev['hooks'][:10]}")
        title = (f"New {dex} pool {sym}/{qsym} on {self.chain}"
                 + (f" ({', '.join(extra)})" if extra else "") + (f", {liq}" if liq else ""))
        return Signal(
            source=self.name, kind=ONCHAIN, title=title, weight=self.weight, chain=self.chain,
            symbol=tm.get("symbol") or entry.get("symbol"), address=token,
            detail={"dex": dex, "factory": factory, "pool": ev["pool"], "pair_token": quote, "event": ev,
                    "tx": lg.get("transactionHash"), "watch_reason": entry.get("reason"),
                    "block": int(lg["blockNumber"], 16) if lg.get("blockNumber") else None},
        )

    def _liquidity(self, ev, token, quote, tm, qm, sym, qsym) -> str | None:
        if ev["kind"] == "v4":
            return None  # V4 liquidity sits in the PoolManager, not a per-pool contract
        parts = []
        for addr, meta, s in ((token, tm, sym), (quote, qm, qsym)):
            try:
                res = self.rpc.call("eth_call", [{"to": addr, "data": "0x70a08231" + _topic(ev["pool"])[2:]},
                                                 "latest"])
                bal = int(res, 16) if res and res != "0x" else 0
            except Exception:
                return None
            dec = meta.get("decimals")
            amt = bal / 10 ** dec if isinstance(dec, int) and 0 <= dec <= 36 else bal
            parts.append(f"{amt:,.4g} {s}")
        return "pool holds " + " + ".join(parts)
