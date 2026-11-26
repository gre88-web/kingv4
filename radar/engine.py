from __future__ import annotations

import logging
import time
from typing import Any

from .alerts import Alerter
from .config import wallets_for
from .correlate import Assessment, assess, severity_at_least
from .models import CODE, EXCHANGE, Signal
from .store import Store
from .watchers.base import Watcher
from .watchers.code import CommitWatcher, FileSnapshotWatcher
from .watchers.dex import DexWatcher
from .watchers.exchange import EXCHANGES
from .watchers.onchain import OnchainWatcher

log = logging.getLogger(__name__)


def build_watchers(cfg: dict[str, Any]) -> tuple[list[Watcher], dict[str, OnchainWatcher]]:
    """Returns (all watchers, onchain watchers by chain). DEX watchers are in the list too;
    find them by type (see dex_watchers)."""
    watchers: list[Watcher] = []
    chains = list((cfg.get("chains") or {}).keys())

    for c in cfg.get("code") or []:
        if not c.get("enabled", True):
            continue
        common = dict(chains=c.get("chains", chains), weight=c.get("weight", 4.0), interval=c.get("interval", 300))
        if c.get("id_pattern"):
            common["id_pattern"] = c["id_pattern"]
        if c.get("prefix_chains"):
            common["prefix_chains"] = c["prefix_chains"]
        if c.get("type", "files") == "files":
            watchers.append(FileSnapshotWatcher(c["name"], c["repo"], c.get("branch", "master"), c["paths"],
                                                downweight=c.get("downweight"),
                                                bulk_threshold=c.get("bulk_threshold", 15), **common))
        else:
            watchers.append(CommitWatcher(c["name"], c["repo"], c.get("branch", "master"),
                                          path_chains=c.get("path_chains"), keywords=c.get("keywords"), **common))

    for name, e in (cfg.get("exchanges") or {}).items():
        if e is False or (isinstance(e, dict) and not e.get("enabled", True)):
            continue
        e = e if isinstance(e, dict) else {}
        watchers.append(EXCHANGES[name](name, interval=e.get("interval", 180), weight=e.get("weight", 4.0),
                                        chains=chains))

    onchain: dict[str, OnchainWatcher] = {}
    for name, ch in (cfg.get("chains") or {}).items():
        if not ch.get("enabled", True):
            continue
        ws = wallets_for(cfg, name)
        if not ws:
            log.warning("chain %s: no wallets configured; onchain watcher idle (edit wallets.yaml)", name)
        w = OnchainWatcher(name, ch["rpc"], ws, max_block_range=ch.get("max_block_range", 1000),
                           confirmations=ch.get("confirmations", 3), lookback_blocks=ch.get("lookback_blocks", 5000),
                           max_blocks_per_poll=ch.get("max_blocks_per_poll", 20000),
                           interval=ch.get("interval", 60))
        onchain[name] = w
        watchers.append(w)
        dex = cfg.get("dex") or {}
        if dex.get("enabled", True) and ch.get("dex", True):
            watchers.append(DexWatcher(
                name, w.rpc, max_block_range=ch.get("max_block_range", 1000),
                confirmations=ch.get("confirmations", 3), backfill_blocks=ch.get("dex_backfill_blocks", 5000),
                watch_days=dex.get("watch_days", 45), weight=dex.get("weight", 3.0),
                token_meta=w.token_meta, interval=ch.get("interval", 60)))
    return watchers, onchain


def dex_watchers(watchers: list[Watcher]) -> dict[str, DexWatcher]:
    return {w.chain: w for w in watchers if isinstance(w, DexWatcher)}


class Engine:
    def __init__(self, cfg: dict[str, Any], store: Store | None = None, alerter: Alerter | None = None,
                 watchers: list[Watcher] | None = None, onchain: dict[str, OnchainWatcher] | None = None) -> None:
        self.cfg = cfg
        self.store = store or Store(cfg["db"])
        self.alerter = alerter or Alerter()
        if watchers is None:
            watchers, onchain = build_watchers(cfg)
        self.watchers = watchers
        self.onchain = onchain or {}
        self.dex = dex_watchers(self.watchers)
        self.min_sev = cfg.get("alert_min_severity", "low")
        self.window = cfg.get("correlation_window_days", 30)
        self.next_due = {w.name: 0.0 for w in self.watchers}

    def process(self, signals: list[Signal]) -> list[Assessment]:
        out = []
        for s in signals:
            self.store.add_signal(s)
            a = assess(self.store, s, window_days=self.window)
            out.append(a)
            if severity_at_least(a.severity, self.min_sev):
                self.alerter.send(a)
            # A code/exchange signal naming a contract: watch it for new DEX pools...
            if s.kind in (CODE, EXCHANGE) and s.address and s.chain in self.dex:
                self.dex[s.chain].watch(self.store, s.address, s.symbol, reason=s.title)
            # ...and check whether the watched wallets are already in it.
            if s.kind in (CODE, EXCHANGE) and s.address and s.chain in self.onchain:
                try:
                    follow = self.onchain[s.chain].check_holdings(self.store, s.address, trigger=s)
                except Exception as e:  # never let a follow-up kill the cycle
                    log.warning("holdings check %s on %s failed: %s", s.address, s.chain, e)
                    follow = []
                out.extend(self.process(follow))
        return out

    def run_due(self, now: float | None = None) -> list[Assessment]:
        now = now if now is not None else time.time()
        results = []
        for w in self.watchers:
            if self.next_due[w.name] > now:
                continue
            self.next_due[w.name] = now + w.interval
            try:
                sigs = w.poll(self.store)
            except Exception as e:
                log.warning("%s: poll failed: %s", w.name, e)
                continue
            if sigs:
                log.info("%s: %d new signal(s)", w.name, len(sigs))
            results.extend(self.process(sigs))
        return results

    def run_forever(self) -> None:
        log.info("radar running: %s", ", ".join(w.name for w in self.watchers))
        while True:
            self.run_due()
            wait = max(1.0, min(self.next_due.values()) - time.time())
            time.sleep(wait)
