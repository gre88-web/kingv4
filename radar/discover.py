"""Find wallets that keep buying tokens *before* they get listed.

For each past listing (token, chain, time), take every ERC-20 transfer in the window
before the announcement and work out who accumulated: received > sent, ignoring
mints, contracts and known infrastructure. Each buyer gets a per-listing score
for how early they bought and how big their position was, and the scores add up
across listings. A wallet that shows up early in several unrelated listings is either
very good or very well informed. Either way it's worth watching.

    radar discover                                # listings.yaml + listings the radar saw itself
    radar discover --pre-days 7 --min-events 2 --out wallets.discovered.yaml

Results are cached per (token, window) in the radar database, so re-ranking is instant.
"""
from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from .store import Store
from .watchers.onchain import RPC, TRANSFER, _addr, iter_logs

log = logging.getLogger(__name__)

ZERO = "0x" + "0" * 40
BURN = {ZERO, "0x000000000000000000000000000000000000dead"}


@dataclass
class Listing:
    chain: str
    address: str
    listed_at: float          # unix seconds (announcement / trading start)
    symbol: str | None = None
    venue: str | None = None

    @property
    def label(self) -> str:
        return self.symbol or self.address[:10]


@dataclass
class Buyer:
    address: str
    events: dict[str, float] = field(default_factory=dict)   # listing label -> score
    detail: dict[str, dict[str, Any]] = field(default_factory=dict)

    @property
    def total(self) -> float:
        return sum(self.events.values())


def parse_time(v: Any) -> float:
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, datetime):
        return (v if v.tzinfo else v.replace(tzinfo=timezone.utc)).timestamp()
    s = str(v).replace("Z", "+00:00")
    d = datetime.fromisoformat(s)
    return (d if d.tzinfo else d.replace(tzinfo=timezone.utc)).timestamp()


def load_listings(path: str | Path) -> list[Listing]:
    p = Path(path)
    if not p.exists():
        return []
    rows = (yaml.safe_load(p.read_text()) or {}).get("listings") or []
    return [Listing(chain=r["chain"], address=str(r["address"]).lower(), listed_at=parse_time(r["listed_at"]),
                    symbol=r.get("symbol"), venue=r.get("venue")) for r in rows]


def listings_from_signals(store: Store, chains: set[str]) -> list[Listing]:
    """Listings the radar itself observed (exchange signals marked listing=True).

    Robinhood/Kraken signals carry only a ticker; resolve it to a contract through the
    code watchers' token snapshots (BitGo knows the address on each chain)."""
    by_symbol: dict[str, list[tuple[str, str]]] = {}
    for _, snap in store.scan("code:", "tokens"):
        for info in snap.values():
            if info.get("symbol") and info.get("address") and info.get("chain") in chains:
                by_symbol.setdefault(info["symbol"].upper(), []).append((info["chain"], info["address"]))
    out, seen = [], set()
    for s in store.recent(100000):
        if s.kind != "exchange" or not s.detail.get("listing"):
            continue
        targets = [(s.chain, s.address)] if s.address and s.chain in chains else by_symbol.get(s.symbol or "", [])
        for chain, addr in targets:
            if (chain, addr) not in seen:
                seen.add((chain, addr))
                out.append(Listing(chain, addr, s.ts, s.symbol, s.detail.get("venue")))
    return out


class Discoverer:
    def __init__(self, store: Store, rpcs: dict[str, RPC], max_ranges: dict[str, int],
                 known: dict[str, str] | None = None, grow_to: int = 4_000_000) -> None:
        self.store, self.rpcs, self.max_ranges = store, rpcs, max_ranges
        self.known = {k.lower(): v for k, v in (known or {}).items()}
        self.grow_to = grow_to

    # ---- chain helpers ----------------------------------------------------------
    def block_at(self, chain: str, ts: float) -> int:
        """First block with timestamp >= ts (binary search, cached)."""
        key = str(int(ts))
        cached = self.store.get(f"block-at:{chain}", key)
        if cached is not None:
            return cached
        rpc = self.rpcs[chain]
        stamp = lambda n: int(rpc.call("eth_getBlockByNumber", [hex(n), False])["timestamp"], 16)
        lo, hi = 0, int(rpc.call("eth_blockNumber", []), 16)
        if stamp(hi) < ts:
            raise ValueError(f"{chain}: {datetime.fromtimestamp(ts, timezone.utc)} is in the future")
        while lo < hi:
            mid = (lo + hi) // 2
            if stamp(mid) < ts:
                lo = mid + 1
            else:
                hi = mid
        self.store.put(f"block-at:{chain}", key, lo)
        return lo

    def is_contract(self, chain: str, addr: str) -> bool:
        cached = self.store.get(f"is-contract:{chain}", addr)
        if cached is None:
            code = self.rpcs[chain].call("eth_getCode", [addr, "latest"])
            # EIP-7702 delegated EOAs have code 0xef0100<addr>; they are still people.
            cached = bool(code and code != "0x" and not code.startswith("0xef0100"))
            self.store.put(f"is-contract:{chain}", addr, cached)
        return cached

    # ---- per listing ------------------------------------------------------------
    def accumulation(self, lst: Listing, pre_days: float) -> dict[str, Any]:
        """Per-address flows of the token in [listed_at - pre_days, listed_at)."""
        start_b = self.block_at(lst.chain, lst.listed_at - pre_days * 86400)
        end_b = self.block_at(lst.chain, lst.listed_at) - 1
        key = f"{lst.address}:{start_b}:{end_b}"
        cached = self.store.get(f"accum:{lst.chain}", key)
        if cached is not None:
            return cached

        t0 = time.time()
        flows: dict[str, dict[str, Any]] = {}
        senders: dict[str, int] = {}
        n = 0
        for chunk in iter_logs(self.rpcs[lst.chain], start_b, end_b, {"address": lst.address, "topics": [TRANSFER]},
                               self.max_ranges.get(lst.chain, 1000), grow_to=self.grow_to):
            for lg in chunk:
                t = lg.get("topics") or []
                if len(t) != 3:
                    continue
                value = int(lg.get("data") or "0x0", 16) if (lg.get("data") or "0x") != "0x" else 0
                if value == 0:
                    continue
                frm, to, blk = _addr(t[1]), _addr(t[2]), int(lg["blockNumber"], 16)
                if frm not in BURN:  # mints are allocations, not buys
                    f = flows.setdefault(to, {"in": 0, "out": 0, "first": blk, "from": {}})
                    f["in"] += value
                    f["first"] = min(f["first"], blk)
                    f["from"][frm] = f["from"].get(frm, 0) + 1
                    senders[frm] = senders.get(frm, 0) + 1
                if frm in flows:
                    flows[frm]["out"] += value
            before, n = n, n + len(chunk)
            if n // 100000 != before // 100000:
                log.info("  %s: %d transfers so far, block %s of %d..%d", lst.label, n,
                         int(chunk[-1]["blockNumber"], 16) if chunk else "?", start_b, end_b)
        log.info("%s on %s: %d transfers in blocks %d..%d (%.0fs)", lst.label, lst.chain, n,
                 start_b, end_b, time.time() - t0)
        # Senders that move the token to many addresses are pools/routers/distributors.
        hubs = sorted(senders, key=senders.get, reverse=True)[:50]
        pools = [h for h in hubs if self.is_contract(lst.chain, h)]
        res = {"start": start_b, "end": end_b, "transfers": n, "pools": pools,
               "flows": {a: {"in": str(f["in"]), "out": str(f["out"]), "first": f["first"],
                             "bought": sum(n for s, n in f["from"].items() if s in pools)}
                         for a, f in flows.items()}}
        self.store.put(f"accum:{lst.chain}", key, res)
        return res

    def score_listing(self, lst: Listing, acc: dict[str, Any]) -> dict[str, tuple[float, dict[str, Any]]]:
        span = max(1, acc["end"] - acc["start"])
        pools = set(acc["pools"])
        holders = []
        for a, f in acc["flows"].items():
            net = int(f["in"]) - int(f["out"])
            if net <= 0 or a in BURN or a == lst.address or a in pools:
                continue
            holders.append((a, net, f))
        if not holders:
            return {}
        # Position size on a log scale between the median holder (0) and the largest (1):
        # percentiles saturate when thousands of wallets hold something.
        nets = sorted(h[1] for h in holders)
        total = sum(nets)
        median, biggest = nets[len(nets) // 2], nets[-1]
        span_log = math.log10(biggest / median) if biggest > median else 1.0
        out = {}
        for a, net, f in holders:
            early = 1 - (f["first"] - acc["start"]) / span          # 1 = at window start, 0 = at listing
            size = min(1.0, max(0.0, math.log10(net / median) / span_log)) if net > median else 0.0
            bought = f["bought"] > 0
            score = 1.0 + early + size + (0.5 if bought else 0.0)
            out[a] = (score, {"early": round(early, 3), "size": round(size, 3), "share": round(net / total, 5), "bought_from_pool": bought,
                              "net": str(net), "first_block": f["first"]})
        return out

    # ---- across listings --------------------------------------------------------
    def run(self, listings: list[Listing], pre_days: float = 10, min_events: int = 1,
            include_contracts: bool = False, limit: int = 25, per_listing_top: int = 300) -> list[Buyer]:
        buyers: dict[str, Buyer] = {}
        for lst in listings:
            if lst.chain not in self.rpcs:
                log.warning("skip %s: no RPC for chain %s", lst.label, lst.chain)
                continue
            try:
                acc = self.accumulation(lst, pre_days)
            except Exception as e:
                log.warning("skip %s on %s: %s", lst.label, lst.chain, e)
                continue
            scored = self.score_listing(lst, acc)
            # Only the strongest holders per listing go forward; dust wallets add nothing.
            top = sorted(scored.items(), key=lambda kv: -kv[1][0])[:per_listing_top]
            for a, (score, det) in top:
                b = buyers.setdefault(a, Buyer(a))
                b.events[lst.label] = round(score, 3)
                b.detail[lst.label] = {**det, "chain": lst.chain}

        ranked = sorted((b for b in buyers.values() if len(b.events) >= min_events),
                        key=lambda b: (-len(b.events), -b.total))
        out = []
        for b in ranked:
            chain = next(iter(b.detail.values()))["chain"]
            if not include_contracts:
                try:
                    if self.is_contract(chain, b.address):
                        continue
                except Exception:
                    pass
            out.append(b)
            if len(out) >= limit:
                break
        return out


def write_wallets(path: str | Path, buyers: list[Buyer]) -> None:
    rows = []
    for i, b in enumerate(buyers, 1):
        chains = sorted({d["chain"] for d in b.detail.values()})
        rows.append({"label": f"early-buyer #{i} ({', '.join(b.events)})", "address": b.address,
                     "kind": "smart_money", "chains": chains,
                     "note": f"score {b.total:.2f} across {len(b.events)} listing(s); review before trusting"})
    Path(path).write_text(
        "# Generated by `radar discover`. Review, then add this file to wallet_files in config.yaml.\n"
        + yaml.safe_dump({"wallets": rows}, sort_keys=False, allow_unicode=True))
