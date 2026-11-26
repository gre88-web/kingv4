"""Diff public, unauthenticated exchange listing endpoints.

An asset often appears in an exchange's public API (as display-only, untradable, or
with trading disabled) before the listing is announced, and the switch to tradable
is the listing itself. Each watcher keeps a snapshot {key: state} and reports new keys
and the state transitions that matter.

Poll politely (minutes, not seconds) and check each exchange's terms for automated access.
"""
from __future__ import annotations

import logging
from typing import Any, Callable

from .. import http
from ..models import EXCHANGE, Signal
from ..store import Store
from .base import Watcher

log = logging.getLogger(__name__)

# Coinbase network id -> radar chain name
COINBASE_NETWORKS = {"ethereum": "ethereum", "base": "base"}


class SnapshotExchangeWatcher(Watcher):
    kind = EXCHANGE
    url: str = ""

    def __init__(self, name: str, interval: float = 180, weight: float = 4.0,
                 chains: list[str] | None = None, sess=None) -> None:
        super().__init__(name, interval)
        self.weight = weight
        self.chains = set(chains) if chains else None
        self.sess = sess or http.session()

    def fetch(self) -> dict[str, dict[str, Any]]:
        raise NotImplementedError

    def changes(self, key: str, old: dict | None, new: dict) -> list[Signal]:
        raise NotImplementedError

    def poll(self, store: Store) -> list[Signal]:
        current = self.fetch()
        ns = f"exchange:{self.name}"
        previous = store.get(ns, "snapshot")
        store.put(ns, "snapshot", current)
        if previous is None:
            log.info("%s: baseline of %d entries", self.name, len(current))
            return []
        out: list[Signal] = []
        for key in sorted(current):
            out.extend(self.changes(key, previous.get(key), current[key]))
        return out

    def _sig(self, title: str, weight: float, symbol: str | None, **kw: Any) -> Signal:
        return Signal(source=self.name, kind=EXCHANGE, title=title, weight=weight, symbol=symbol, **kw)


class RobinhoodWatcher(SnapshotExchangeWatcher):
    url = "https://nummus.robinhood.com/currency_pairs/"

    def fetch(self) -> dict[str, dict[str, Any]]:
        data = http.request(self.sess, "GET", self.url).json()
        out = {}
        for p in data.get("results", []):
            a = p.get("asset_currency") or {}
            code = a.get("code") or p.get("symbol")
            if not code:
                continue
            out[code] = {
                "name": a.get("name"),
                "pair": p.get("display_symbol") or p.get("symbol"),
                "tradability": p.get("tradability"),
                "display_only": bool(p.get("display_only")),
            }
        return out

    def changes(self, key, old, new):
        if old is None:
            state = "tradable" if new["tradability"] == "tradable" else "not tradable yet"
            return [self._sig(f"Robinhood: new asset {key} ({new['name']}), {state}",
                              self.weight + (1 if state == "tradable" else 0), key, detail=new)]
        if old.get("tradability") != "tradable" and new.get("tradability") == "tradable":
            return [self._sig(f"Robinhood: {key} ({new['name']}) became TRADABLE", self.weight + 1, key,
                              detail={**new, "was": old.get("tradability")})]
        return []


class CoinbaseCurrenciesWatcher(SnapshotExchangeWatcher):
    url = "https://api.exchange.coinbase.com/currencies"

    def fetch(self):
        out = {}
        for c in http.request(self.sess, "GET", self.url).json():
            nets = {n["id"]: (n.get("contract_address") or "").lower() or None
                    for n in c.get("supported_networks") or [] if n.get("id")}
            out[c["id"]] = {"name": c.get("name"), "status": c.get("status"), "networks": nets}
        return out

    def _onchain(self, networks: dict[str, str | None]) -> list[tuple[str, str | None]]:
        res = []
        for net, addr in networks.items():
            chain = COINBASE_NETWORKS.get(net)
            if chain and (not self.chains or chain in self.chains):
                res.append((chain, addr))
        return res

    def changes(self, key, old, new):
        out = []
        if old is None:
            targets = self._onchain(new["networks"]) or [(None, None)]
            for chain, addr in targets:
                where = f" on {chain}" if chain else ""
                out.append(self._sig(f"Coinbase: new currency {key} ({new['name']}){where}", self.weight, key,
                                     chain=chain, address=addr, detail=new))
            return out
        if old.get("status") != "online" and new.get("status") == "online":
            out.append(self._sig(f"Coinbase: {key} status {old.get('status')} -> online", self.weight - 1, key,
                                 detail=new))
        added = {k: v for k, v in new["networks"].items() if k not in old.get("networks", {})}
        for chain, addr in self._onchain(added):
            out.append(self._sig(f"Coinbase: {key} adds {chain} network", self.weight / 2, key,
                                 chain=chain, address=addr, detail=new))
        return out


class CoinbaseProductsWatcher(SnapshotExchangeWatcher):
    url = "https://api.exchange.coinbase.com/products"

    def fetch(self):
        return {p["id"]: {"base": p.get("base_currency"), "status": p.get("status"),
                          "trading_disabled": bool(p.get("trading_disabled"))}
                for p in http.request(self.sess, "GET", self.url).json()}

    def changes(self, key, old, new):
        if old is None:
            note = "trading disabled" if new["trading_disabled"] else new["status"]
            return [self._sig(f"Coinbase: new product {key} ({note})", self.weight, new["base"], detail=new)]
        if old.get("trading_disabled") and not new["trading_disabled"]:
            return [self._sig(f"Coinbase: {key} trading ENABLED", self.weight, new["base"], detail=new)]
        return []


class KrakenAssetsWatcher(SnapshotExchangeWatcher):
    url = "https://api.kraken.com/0/public/Assets"

    def fetch(self):
        data = http.request(self.sess, "GET", self.url).json()
        if data.get("error"):
            raise http.HttpError(f"kraken: {data['error']}")
        return {k: {"altname": v.get("altname"), "status": v.get("status")} for k, v in data["result"].items()}

    def changes(self, key, old, new):
        sym = new.get("altname") or key
        if old is None:
            return [self._sig(f"Kraken: new asset {sym} ({new.get('status')})", self.weight, sym, detail=new)]
        if old.get("status") != "enabled" and new.get("status") == "enabled":
            return [self._sig(f"Kraken: {sym} status {old.get('status')} -> enabled", self.weight - 1, sym,
                              detail=new)]
        return []


EXCHANGES: dict[str, Callable[..., SnapshotExchangeWatcher]] = {
    "robinhood": RobinhoodWatcher,
    "coinbase_currencies": CoinbaseCurrenciesWatcher,
    "coinbase_products": CoinbaseProductsWatcher,
    "kraken": KrakenAssetsWatcher,
}
