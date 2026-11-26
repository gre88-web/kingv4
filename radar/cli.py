from __future__ import annotations

import argparse
import logging
import sys
import time
from collections import defaultdict
from pathlib import Path
from datetime import datetime, timezone

from . import config as config_mod
from . import http
from .correlate import COMMON_SYMBOLS
from .engine import Engine, build_watchers
from .store import Store
from .watchers.code import RAW, FileSnapshotWatcher
from .watchers.exchange import SnapshotExchangeWatcher
from .watchers.onchain import OnchainWatcher


def _fmt_ts(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d %H:%M")


def cmd_run(args, cfg) -> int:
    engine = Engine(cfg)
    if args.once:
        res = engine.run_due()
        print(f"done: {len(res)} signal(s)")
        return 0
    try:
        engine.run_forever()
    except KeyboardInterrupt:
        pass
    return 0


def cmd_signals(args, cfg) -> int:
    store = Store(cfg["db"])
    for s in reversed(store.recent(args.limit, since=time.time() - args.days * 86400)):
        print(f"{_fmt_ts(s.ts)}Z  w={s.weight:<4g} {s.kind:<8} {s.title}")
    return 0


def cmd_candidates(args, cfg) -> int:
    """Group recent signals by token and rank by combined score."""
    store = Store(cfg["db"])
    sigs = store.recent(100000, since=time.time() - args.days * 86400)
    # union-find over address/symbol so one token's code, exchange and onchain hits merge
    parent: dict[str, str] = {}

    def find(x: str) -> str:
        while parent.setdefault(x, x) != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def keys(s):
        k = []
        if s.address:
            k.append("a:" + s.address)
        if s.symbol and s.symbol not in COMMON_SYMBOLS:
            k.append("s:" + s.symbol)
        return k

    for s in sigs:
        ks = keys(s)
        for k in ks[1:]:
            parent[find(k)] = find(ks[0])
    groups: dict[str, list] = defaultdict(list)
    for s in sigs:
        ks = keys(s)
        if ks:
            groups[find(ks[0])].append(s)

    rows = []
    for g in groups.values():
        best: dict[str, float] = {}
        for s in g:
            best[s.source] = max(best.get(s.source, 0), s.weight)
        kinds = {s.kind for s in g}
        score = sum(best.values()) + 2.0 * (len(kinds) - 1)
        sym = next((s.symbol for s in g if s.symbol), None)
        addr = next((s.address for s in g if s.address), None)
        rows.append((score, len(kinds), sym, addr, min(s.ts for s in g), g))
    rows.sort(key=lambda r: (-r[1], -r[0]))
    for score, nk, sym, addr, first, g in rows[: args.limit]:
        print(f"{score:5.1f}  kinds={nk}  {sym or '?':<12} {addr or '':<42}  first {_fmt_ts(first)}Z  "
              f"sources: {', '.join(sorted({s.source for s in g}))}")
    return 0


def cmd_discover(args, cfg) -> int:
    from .discover import Discoverer, listings_from_signals, load_listings, write_wallets
    from .watchers.onchain import RPC

    store = Store(cfg["db"])
    chains = cfg.get("chains") or {}
    listings = load_listings(Path(args.config).resolve().parent / args.listings)
    if not args.no_signals:
        have = {(l.chain, l.address) for l in listings}
        listings += [l for l in listings_from_signals(store, set(chains)) if (l.chain, l.address) not in have]
    if args.chain:
        listings = [l for l in listings if l.chain in args.chain]
    if not listings:
        print(f"no listings: add some to {args.listings}, or let `radar run` observe a few")
        return 1
    print(f"{len(listings)} listing(s): " + ", ".join(f"{l.label}@{l.chain}" for l in listings))
    known = {w["address"]: w["label"] for w in cfg["wallets"]}
    d = Discoverer(store, {n: RPC(c["rpc"]) for n, c in chains.items()},
                   {n: c.get("max_block_range", 1000) for n, c in chains.items()}, known=known)
    buyers = d.run(listings, pre_days=args.pre_days, min_events=args.min_events,
                   include_contracts=args.include_contracts, limit=args.limit)
    if not buyers:
        print("no wallets matched")
        return 0
    print(f"\n{'#':>3}  {'address':<42}  {'hits':>4}  {'score':>6}  listings (earliness, size, share of net buying)")
    for i, b in enumerate(buyers, 1):
        parts = [f"{k} ({v['early']:.2f}, {v['size']:.2f}, {100 * v['share']:.2f}%"
                 f"{', pool buy' if v['bought_from_pool'] else ''})"
                 for k, v in b.detail.items()]
        tag = f"  [{known[b.address]}]" if b.address in known else ""
        print(f"{i:>3}  {b.address}  {len(b.events):>4}  {b.total:>6.2f}  {'; '.join(parts)}{tag}")
    if args.out:
        write_wallets(Path(args.config).resolve().parent / args.out, buyers)
        print(f"\nwrote {len(buyers)} wallet(s) to {args.out}; review it, then add it to wallet_files")
    return 0


def cmd_check(args, cfg) -> int:
    """Probe every configured endpoint once without touching the database."""
    watchers, _ = build_watchers(cfg)
    ok = True
    sess = http.session()
    for w in watchers:
        try:
            if isinstance(w, OnchainWatcher):
                cid = int(w.rpc.call("eth_chainId", []), 16)
                head = int(w.rpc.call("eth_blockNumber", []), 16)
                exp = config_mod.EXPECTED_CHAIN_IDS.get(w.chain)
                good = exp is None or exp == cid
                ok &= good
                print(f"{'OK ' if good else 'BAD'} {w.name}: chainId {cid} head {head}, {len(w.wallets)} wallet(s)"
                      + ("" if good else f" (expected {exp})"))
            elif isinstance(w, SnapshotExchangeWatcher):
                print(f"OK  {w.name}: {len(w.fetch())} entries")
            elif isinstance(w, FileSnapshotWatcher):
                for p in w.paths:
                    http.request(sess, "HEAD", RAW.format(repo=w.repo, branch=w.branch, path=p))
                print(f"OK  {w.name}: {len(w.paths)} file(s) reachable")
            else:
                print(f"--  {w.name}: not probed (GitHub API watcher)")
        except Exception as e:
            ok = False
            print(f"ERR {w.name}: {e}")
    if not cfg["wallets"]:
        print("NOTE: no wallets configured; add labeled addresses to wallets.yaml for onchain signals")
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="radar", description="Public-data listing radar")
    ap.add_argument("-c", "--config", default="config.yaml")
    ap.add_argument("-v", "--verbose", action="store_true")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="poll all sources and alert")
    r.add_argument("--once", action="store_true", help="one pass over every watcher, then exit")
    s = sub.add_parser("signals", help="list recent signals")
    s.add_argument("--limit", type=int, default=50)
    s.add_argument("--days", type=float, default=7)
    c = sub.add_parser("candidates", help="rank tokens by combined evidence")
    c.add_argument("--limit", type=int, default=25)
    c.add_argument("--days", type=float, default=30)
    sub.add_parser("check", help="probe endpoints and RPCs")
    d = sub.add_parser("discover", help="find wallets that bought early before past listings")
    d.add_argument("--listings", default="listings.yaml", help="past listings file (relative to config)")
    d.add_argument("--no-signals", action="store_true", help="ignore listings observed by `radar run`")
    d.add_argument("--chain", nargs="*", help="only listings on these chains")
    d.add_argument("--pre-days", type=float, default=10, help="window before each listing")
    d.add_argument("--min-events", type=int, default=1, help="require early buys in at least N listings")
    d.add_argument("--include-contracts", action="store_true", help="keep contract wallets (smart accounts, MM vaults)")
    d.add_argument("--limit", type=int, default=25)
    d.add_argument("--out", help="write results as a wallets file, e.g. wallets.discovered.yaml")
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    cfg = config_mod.load(args.config)
    return {"run": cmd_run, "signals": cmd_signals, "candidates": cmd_candidates, "check": cmd_check,
            "discover": cmd_discover}[args.cmd](args, cfg)


if __name__ == "__main__":
    sys.exit(main())
