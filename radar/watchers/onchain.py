"""Watch labeled wallets (market makers, exchanges, teams) for first-time token flows.

Plain JSON-RPC ``eth_getLogs`` on ERC-20 ``Transfer`` events, so the same code serves
Ethereum, Base, Robinhood Chain and Ink with no explorer API keys. One query per block
chunk covers every watched wallet (topics accept OR-lists).

What gets reported:
* a wallet receiving a token it has never received before (since tracking began)
* a wallet *sending* a token for the first time. If the transaction was also sent by
  that wallet, this is "verified": a spam token can fake Transfer events, but it cannot
  make a market maker sign a transaction.

Noise control: zero-value transfers (address poisoning) are dropped, and so are tokens
whose name/symbol looks like airdrop spam (URLs, "claim", "visit"...).
"""
from __future__ import annotations

import logging
import re
from typing import Any, Iterator

from .. import http
from ..models import ONCHAIN, Signal
from ..store import Store
from .base import Watcher

log = logging.getLogger(__name__)

TRANSFER = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
SPAM_RE = re.compile(r"https?:|www\.|\.(com|io|org|net|xyz|app|gg|site|top|me)\b|t\.me|claim|visit|reward|airdrop|"
                     r"voucher|bonus|\$\s?\d|access|eligible", re.I)
RANGE_ERR_RE = re.compile(r"range|limit|too many|exceed|10000|response size|timeout", re.I)

KIND_WEIGHT = {"market_maker": 3.0, "exchange": 3.0, "fund": 2.5, "smart_money": 2.5, "team": 2.0, "other": 1.5}


def _topic(addr: str) -> str:
    return "0x" + addr.lower().removeprefix("0x").rjust(64, "0")


def _addr(topic: str) -> str:
    return "0x" + topic[-40:].lower()


def _decode_string(hexdata: str) -> str | None:
    b = bytes.fromhex(hexdata.removeprefix("0x") or "")
    if not b:
        return None
    try:
        if len(b) >= 64:  # ABI-encoded dynamic string
            off = int.from_bytes(b[0:32], "big")
            ln = int.from_bytes(b[off:off + 32], "big")
            if off + 32 + ln <= len(b):
                return b[off + 32: off + 32 + ln].decode("utf-8", "replace").strip("\x00").strip() or None
        return b[:32].rstrip(b"\x00").decode("utf-8", "replace").strip() or None  # bytes32 (old tokens)
    except Exception:
        return None


class RPC:
    def __init__(self, url: str, sess=None) -> None:
        self.url = url
        self.sess = sess or http.session()
        self._id = 0

    def call(self, method: str, params: list[Any]) -> Any:
        self._id += 1
        r = http.request(self.sess, "POST", self.url, json={"jsonrpc": "2.0", "id": self._id,
                                                            "method": method, "params": params})
        data = r.json()
        if "error" in data:
            raise RPCError(data["error"].get("message", str(data["error"])))
        return data["result"]


class RPCError(RuntimeError):
    pass


def iter_logs(rpc: RPC, frm: int, to: int, flt: dict[str, Any], max_range: int,
              grow_to: int | None = None, target_results: int = 5000) -> Iterator[list[dict[str, Any]]]:
    """eth_getLogs over [frm, to], yielded chunk by chunk (so callers can aggregate as they go).

    The chunk halves when the provider rejects the range or result size. When
    ``grow_to`` is set, each next chunk is resized (x0.5 to x2, up to ``grow_to``) to aim at
    ``target_results`` logs, for narrow filters (one token) scanned over millions of
    blocks where providers cap results rather than ranges.
    """
    start, step = frm, max_range
    while start <= to:
        end = min(to, start + step - 1)
        try:
            got = rpc.call("eth_getLogs", [{**flt, "fromBlock": hex(start), "toBlock": hex(end)}])
        except (RPCError, http.HttpError) as e:
            if step > 1 and RANGE_ERR_RE.search(str(e)):
                step = max(1, step // 2)
                log.debug("shrinking log range to %d (%s)", step, e)
                continue
            raise
        yield got
        start = end + 1
        if grow_to:
            factor = min(2.0, max(0.5, target_results / max(1, len(got))))
            step = max(1, min(grow_to, int(step * factor)))


def fetch_logs(rpc: RPC, frm: int, to: int, flt: dict[str, Any], max_range: int, **kw: Any) -> list[dict[str, Any]]:
    return [lg for chunk in iter_logs(rpc, frm, to, flt, max_range, **kw) for lg in chunk]


class OnchainWatcher(Watcher):
    kind = ONCHAIN

    def __init__(self, chain: str, rpc_url: str, wallets: list[dict[str, Any]], *,
                 max_block_range: int = 1000, confirmations: int = 3, lookback_blocks: int = 5000,
                 max_blocks_per_poll: int = 20000, interval: float = 60, rpc: RPC | None = None) -> None:
        super().__init__(f"onchain:{chain}", interval)
        self.chain = chain
        self.rpc = rpc or RPC(rpc_url)
        self.wallets = {w["address"].lower(): w for w in wallets}
        self.max_range = max_block_range
        self.confirmations = confirmations
        self.lookback = lookback_blocks
        self.max_per_poll = max_blocks_per_poll

    # ---- RPC helpers ------------------------------------------------------
    def _logs_adaptive(self, frm: int, to: int, topics: list[Any]) -> list[dict[str, Any]]:
        return fetch_logs(self.rpc, frm, to, {"topics": topics}, self.max_range)

    def token_meta(self, store: Store, token: str) -> dict[str, Any]:
        ns = f"tokens:{self.chain}"
        meta = store.get(ns, token)
        if meta is not None:
            return meta
        meta = {"symbol": None, "name": None, "decimals": None}
        for field, sel in (("symbol", "0x95d89b41"), ("name", "0x06fdde03"), ("decimals", "0x313ce567")):
            try:
                res = self.rpc.call("eth_call", [{"to": token, "data": sel}, "latest"])
                meta[field] = int(res, 16) if field == "decimals" and res not in ("0x", None) else (
                    _decode_string(res) if field != "decimals" else None)
            except Exception:
                pass
        store.put(ns, token, meta)
        return meta

    # ---- main loop --------------------------------------------------------
    def poll(self, store: Store) -> list[Signal]:
        if not self.wallets:
            return []
        ns = f"cursor:{self.chain}"
        head = int(self.rpc.call("eth_blockNumber", []), 16) - self.confirmations
        cursor = store.get(ns, "block")
        warmup = cursor is None
        if warmup:
            cursor = max(0, head - self.lookback)
        frm, to = cursor + 1, min(head, cursor + self.max_per_poll)
        if frm > to:
            return []

        topics_wallets = [_topic(a) for a in self.wallets]
        incoming = self._logs_adaptive(frm, to, [TRANSFER, None, topics_wallets])
        outgoing = self._logs_adaptive(frm, to, [TRANSFER, topics_wallets])

        signals: list[Signal] = []
        for direction, logs in (("in", incoming), ("out", outgoing)):
            for lg in logs:
                s = self._handle(store, direction, lg, warmup)
                if s:
                    signals.append(s)
        store.put(ns, "block", to)
        if warmup:
            log.info("%s: warmed up blocks %d..%d, %d first-seen pairs recorded silently",
                     self.name, frm, to, len(incoming) + len(outgoing))
        return signals

    def _handle(self, store: Store, direction: str, lg: dict[str, Any], warmup: bool) -> Signal | None:
        topics = lg.get("topics") or []
        if len(topics) < 3:  # ERC-721 has 4 topics; ERC-20 has 3 with value in data. Skip malformed.
            return None
        if len(topics) == 4:
            return None  # NFT transfer
        value = int(lg.get("data") or "0x0", 16) if (lg.get("data") or "0x") != "0x" else 0
        if value == 0:
            return None  # address-poisoning / zero-value spam
        token = lg["address"].lower()
        frm, to = _addr(topics[1]), _addr(topics[2])
        wallet = to if direction == "in" else frm
        if wallet not in self.wallets:
            return None
        if not store.mark_seen(f"flow:{self.chain}:{direction}", f"{wallet}:{token}") or warmup:
            return None

        meta = self.token_meta(store, token)
        label = f"{meta.get('name') or ''} {meta.get('symbol') or ''}"
        if SPAM_RE.search(label):
            return None

        w = self.wallets[wallet]
        weight = KIND_WEIGHT.get(w.get("kind", "other"), 1.5)
        verified = False
        if direction == "out":
            try:
                tx = self.rpc.call("eth_getTransactionByHash", [lg["transactionHash"]])
                verified = bool(tx) and (tx.get("from") or "").lower() == wallet
            except Exception:
                pass
            weight += 1.0 if verified else -0.5

        dec = meta.get("decimals")
        amount = value / 10 ** dec if isinstance(dec, int) and 0 <= dec <= 36 else value
        counterparty = frm if direction == "in" else to
        cp_label = self.wallets.get(counterparty, {}).get("label")
        sym = meta.get("symbol") or token[:10]
        verb = "received" if direction == "in" else "sent"
        title = (f"{w['label']} {verb} first-ever {sym} on {self.chain}: {amount:,.4g}"
                 + (f" {'from' if direction == 'in' else 'to'} {cp_label}" if cp_label else "")
                 + (" (tx signed by wallet)" if verified else ""))
        return Signal(
            source=self.name, kind=ONCHAIN, title=title, weight=weight, chain=self.chain,
            symbol=meta.get("symbol"), address=token,
            detail={"wallet": wallet, "wallet_label": w["label"], "wallet_kind": w.get("kind"),
                    "direction": direction, "counterparty": counterparty, "counterparty_label": cp_label,
                    "amount": amount, "token_name": meta.get("name"), "tx": lg.get("transactionHash"),
                    "block": int(lg["blockNumber"], 16) if lg.get("blockNumber") else None,
                    "verified_sender": verified},
        )

    # ---- follow-up on tokens flagged by other sources -------------------------
    def check_holdings(self, store: Store, token: str, trigger: Signal | None = None) -> list[Signal]:
        """balanceOf(token) for every watched wallet. Non-zero = someone is already positioned."""
        token = token.lower()
        if not store.mark_seen(f"holdings:{self.chain}", token):
            return []
        meta = self.token_meta(store, token)
        dec = meta.get("decimals")
        out = []
        for wallet, w in self.wallets.items():
            try:
                res = self.rpc.call("eth_call", [{"to": token, "data": "0x70a08231" + _topic(wallet)[2:]}, "latest"])
                bal = int(res, 16) if res and res != "0x" else 0
            except Exception:
                continue
            if bal == 0:
                continue
            amount = bal / 10 ** dec if isinstance(dec, int) and 0 <= dec <= 36 else bal
            sym = meta.get("symbol") or token[:10]
            out.append(Signal(
                source=self.name, kind=ONCHAIN, chain=self.chain, symbol=meta.get("symbol"), address=token,
                weight=KIND_WEIGHT.get(w.get("kind", "other"), 1.5),
                title=f"{w['label']} already holds {amount:,.4g} {sym} on {self.chain}",
                detail={"wallet": wallet, "wallet_label": w["label"], "wallet_kind": w.get("kind"),
                        "balance": amount, "token_name": meta.get("name"),
                        "triggered_by": trigger.title if trigger else None},
            ))
        return out
