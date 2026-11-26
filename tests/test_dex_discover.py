from __future__ import annotations

import calendar

import pytest

from radar.discover import Discoverer, Listing, listings_from_signals, load_listings, write_wallets
from radar.engine import Engine
from radar.keccak import keccak256, topic
from radar.models import CODE, EXCHANGE, Signal
from radar.store import Store
from radar.watchers.dex import V4, DexWatcher, EVENTS, decode_pool_event
from radar.watchers.onchain import TRANSFER, RPCError, _topic, iter_logs

from .test_radar import CASHCAT, ListAlerter, StubWatcher, _abi_str

WETH = "0x4200000000000000000000000000000000000006"
POOL = "0x" + "3" * 40
V2 = next(k for k, v in EVENTS.items() if v == "v2")
V3 = next(k for k, v in EVENTS.items() if v == "v3")


def _w(x: int | str) -> str:
    return (x[2:] if isinstance(x, str) else format(x, "x")).rjust(64, "0")


@pytest.fixture
def store(tmp_path):
    return Store(str(tmp_path / "t.db"))


def test_keccak_known_vectors():
    assert keccak256(b"").hex() == "c5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470"
    assert topic("Transfer(address,address,uint256)") == TRANSFER


def test_decode_v2_v3_v4():
    v2 = {"topics": [V2, _topic(CASHCAT), _topic(WETH)], "data": "0x" + _w(POOL) + _w(7)}
    assert decode_pool_event(v2) == {"kind": "v2", "token0": CASHCAT, "token1": WETH, "pool": POOL}
    v3 = {"topics": [V3, _topic(CASHCAT), _topic(WETH), "0x" + _w(3000)], "data": "0x" + _w(60) + _w(POOL)}
    assert decode_pool_event(v3)["pool"] == POOL and decode_pool_event(v3)["fee"] == 3000
    pid = "0x" + "ab" * 32
    v4 = {"topics": [V4, pid, _topic("0x" + "0" * 40), _topic(CASHCAT)],
          "data": "0x" + _w(0x800000) + _w(60) + _w("0x" + "4" * 40) + _w(1) + _w(0)}
    d = decode_pool_event(v4)
    assert d["token1"] == CASHCAT and d["pool"] == pid and d["hooks"] == "0x" + "4" * 40


class DexRPC:
    def __init__(self, head, logs, meta=None, balances=None):
        self.head, self.logs, self.meta, self.balances = head, logs, meta or {}, balances or {}
        self.calls = []

    def call(self, method, params):
        if method == "eth_blockNumber":
            return hex(self.head)
        if method == "eth_getLogs":
            f = params[0]
            frm, to = int(f["fromBlock"], 16), int(f["toBlock"], 16)
            self.calls.append((frm, to))
            out = []
            for lg in self.logs:
                if not frm <= int(lg["blockNumber"], 16) <= to:
                    continue
                ok = True
                for i, want in enumerate(f["topics"]):
                    if want is None:
                        continue
                    want = want if isinstance(want, list) else [want]
                    if i >= len(lg["topics"]) or lg["topics"][i] not in want:
                        ok = False
                if ok:
                    out.append(lg)
            return out
        if method == "eth_call":
            to, data = params[0]["to"], params[0]["data"]
            if data.startswith("0x70a08231"):
                return hex(self.balances.get((to, "0x" + data[-40:]), 0))
            if data == "0x95d89b41":
                return _abi_str(self.meta.get(to, {}).get("symbol", ""))
            return hex(18)
        raise AssertionError(method)


def _meta(rpc):
    def f(store, token):
        return {"symbol": rpc.meta.get(token, {}).get("symbol"), "decimals": 18}
    return f


def test_dex_watcher_finds_pool_for_watched_token(store):
    lg = {"address": "0x420dd381b31aef6683db6b902084cb0ffece40da",
          "topics": [next(k for k, v in EVENTS.items() if v == "solidly"), _topic(CASHCAT), _topic(WETH), "0x" + _w(0)],
          "data": "0x" + _w(POOL) + _w(1), "blockNumber": hex(990), "transactionHash": "0x1", "logIndex": "0x0"}
    rpc = DexRPC(1000, [lg], meta={CASHCAT: {"symbol": "CASHCAT"}, WETH: {"symbol": "WETH"}},
                 balances={(CASHCAT, POOL): 10**24, (WETH, POOL): 5 * 10**18})
    w = DexWatcher("base", rpc, confirmations=0, backfill_blocks=50, token_meta=_meta(rpc))
    assert w.poll(store) == []                          # nothing watched: just tracks head
    assert not w.watch(store, WETH, "WETH")             # common tokens are never watched
    assert w.watch(store, CASHCAT, "CASHCAT", "bitgo")
    [s] = w.poll(store)                                 # found via backfill
    assert s.address == CASHCAT and "Aerodrome pool CASHCAT/WETH" in s.title and "5 WETH" in s.title
    rpc.head = 1100
    assert w.poll(store) == []                          # same pool never alerts twice


def test_engine_adds_flagged_token_to_dex_watchlist(store):
    rpc = DexRPC(1000, [])
    dex = DexWatcher("robinhood", rpc, confirmations=0, token_meta=_meta(rpc))
    code = StubWatcher("bitgo", [Signal("bitgo", CODE, "adds cashcat", 4, "robinhood", "CASHCAT", CASHCAT)])
    Engine({"db": ":memory:"}, store=store, alerter=ListAlerter(), watchers=[code, dex]).run_due(now=0)
    assert CASHCAT in store.get("watchlist", "robinhood")


def test_iter_logs_resizes_toward_target():
    class R:
        def __init__(self):
            self.ranges = []

        def call(self, method, params):
            f = params[0]
            a, b = int(f["fromBlock"], 16), int(f["toBlock"], 16)
            self.ranges.append(b - a + 1)
            if b - a + 1 > 4000:
                raise RPCError("logs matched by query exceeds limit of 10000")
            return [{}] * ((b - a + 1) // 2)    # 1 log per 2 blocks
    r = R()
    total = sum(len(c) for c in iter_logs(r, 0, 99_999, {}, 1000, grow_to=1_000_000, target_results=1000))
    assert total == 50_000
    assert max(x for x in r.ranges if x <= 4000) >= 1900      # grew from 1000 toward ~2000 blocks


# ---------------------------------------------------------------- discovery
class ChainRPC:
    """Blocks 0..1000 with timestamp = T0 + block; transfers given per test."""
    T0 = 1_700_000_000

    def __init__(self, logs, contracts=()):
        self.logs, self.contracts = logs, set(contracts)

    def call(self, method, params):
        if method == "eth_blockNumber":
            return hex(1000)
        if method == "eth_getBlockByNumber":
            return {"timestamp": hex(self.T0 + int(params[0], 16))}
        if method == "eth_getLogs":
            f = params[0]
            a, b = int(f["fromBlock"], 16), int(f["toBlock"], 16)
            return [lg for lg in self.logs if a <= int(lg["blockNumber"], 16) <= b and lg["address"] == f["address"]]
        if method == "eth_getCode":
            return "0x6080" if params[0] in self.contracts else "0x"
        raise AssertionError(method)


def _xfer(token, frm, to, value, block):
    return {"address": token, "topics": [TRANSFER, _topic(frm), _topic(to)], "data": hex(value),
            "blockNumber": hex(block)}


A, B, C, POOLC = ("0x" + c * 40 for c in "abcd")
TOK2 = "0x" + "e" * 40


def test_discovery_ranks_repeat_early_buyers(store):
    logs = [
        # Listing 1 (CASHCAT, listed at block 500): A buys early and big from the pool, B late and small,
        # C buys then dumps everything.
        _xfer(CASHCAT, "0x" + "0" * 40, POOLC, 10**30, 10),      # mint to pool (ignored as a buy)
        _xfer(CASHCAT, POOLC, A, 10**24, 120),
        _xfer(CASHCAT, POOLC, B, 10**21, 480),
        _xfer(CASHCAT, POOLC, C, 10**24, 130),
        _xfer(CASHCAT, C, POOLC, 10**24, 200),
        _xfer(CASHCAT, POOLC, A, 10**22, 499),
        # Listing 2 (TOK2, listed at block 900): A early again.
        _xfer(TOK2, POOLC, A, 10**23, 820),
        _xfer(TOK2, POOLC, B, 10**20, 899),
    ]
    rpc = ChainRPC(logs, contracts={POOLC})
    d = Discoverer(store, {"robinhood": rpc}, {"robinhood": 200})
    T = ChainRPC.T0
    listings = [Listing("robinhood", CASHCAT, T + 500, "CASHCAT"), Listing("robinhood", TOK2, T + 900, "TOK2")]
    pre = 400 / 86400
    ranked = d.run(listings, pre_days=pre)
    assert [b.address for b in ranked][:2] == [A, B]
    assert set(ranked[0].events) == {"CASHCAT", "TOK2"} and ranked[0].total > ranked[1].total
    assert C not in {b.address for b in ranked}                 # sold out before listing
    assert POOLC not in {b.address for b in ranked}             # pools excluded
    assert ranked[0].detail["CASHCAT"]["bought_from_pool"]
    assert [b.address for b in d.run(listings, pre_days=pre, min_events=2)] == [A, B]


def test_listings_from_signals_resolves_symbol_via_bitgo_snapshot(store, tmp_path):
    store.put("code:bitgo-statics", "tokens", {"hoodeth:cashcat": {"chain": "robinhood", "symbol": "CASHCAT",
                                                                     "address": CASHCAT}})
    store.add_signal(Signal("robinhood", EXCHANGE, "Robinhood: CASHCAT became TRADABLE", 5, symbol="CASHCAT",
                            detail={"listing": True, "venue": "Robinhood"}))
    store.add_signal(Signal("robinhood", EXCHANGE, "Robinhood: new asset X, not tradable", 4, symbol="X",
                            detail={"listing": False}))
    [l] = listings_from_signals(store, {"robinhood", "base"})
    assert (l.chain, l.address, l.symbol, l.venue) == ("robinhood", CASHCAT, "CASHCAT", "Robinhood")

    p = tmp_path / "l.yaml"
    p.write_text(f"listings:\n  - {{chain: robinhood, address: '{CASHCAT}', listed_at: 2026-08-06T00:00:00Z}}\n")
    [l] = load_listings(p)
    assert l.listed_at == calendar.timegm((2026, 8, 6, 0, 0, 0))


def test_write_wallets_round_trips_into_config(tmp_path):
    from radar import config as cfgmod
    from radar.discover import Buyer
    write_wallets(tmp_path / "wallets.discovered.yaml",
                  [Buyer(A, {"CASHCAT": 3.2}, {"CASHCAT": {"chain": "robinhood"}})])
    (tmp_path / "config.yaml").write_text("wallet_files: [wallets.discovered.yaml]\n")
    [w] = cfgmod.load(str(tmp_path / "config.yaml"))["wallets"]
    assert w["address"] == A and w["kind"] == "smart_money" and w["chains"] == ["robinhood"]
