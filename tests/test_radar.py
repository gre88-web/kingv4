from __future__ import annotations

import json

import pytest

from radar.alerts import format_alert
from radar.correlate import assess
from radar.engine import Engine
from radar.extract import extract_tokens, net_added_lines
from radar.models import CODE, EXCHANGE, ONCHAIN, Signal
from radar.store import Store
from radar.watchers.code import CommitWatcher, FileSnapshotWatcher
from radar.watchers.exchange import CoinbaseCurrenciesWatcher, RobinhoodWatcher
from radar.watchers.onchain import TRANSFER, OnchainWatcher, _topic

CASHCAT = "0x020bfc650a365f8bb26819deaabf3e21291018b4"
MM = "0x1111111111111111111111111111111111111111"
EXCH = "0x2222222222222222222222222222222222222222"

# Layout copied from BitGo's modules/statics/src/coins/hoodethTokens.ts
BITGO_BEFORE = """
export const hoodethTokens = [
  erc20Token(
    'eada9a10-3d17-465f-978b-5a183e73f4c6',
    'hoodeth:nvda',
    'NVIDIA Corporation • Robinhood',
    18,
    '0xd0601ce157db5bdc3162bbac2a2c8af5320d9eec',
    UnderlyingAsset['hoodeth:nvda'],
    Networks.main.hoodeth,
  ),
];
"""
BITGO_AFTER = BITGO_BEFORE.replace("];", f"""  erc20Token(
    '0519b754-a119-4431-9d00-490522e2a4d1',
    'hoodeth:cashcat',
    'Cash Cat',
    18,
    '{CASHCAT}',
    UnderlyingAsset['hoodeth:cashcat'],
    Networks.main.hoodeth,
  ),
  erc20Token(
    'f4e2c9a2-130f-4080-ba53-d43d5494ee2b',
    'hoodeth:pltr',
    'Palantir Technologies Inc. • Robinhood',
    18,
    '0xb0992820e760d836549ba69bc7598b4af75dee03',
    UnderlyingAsset['hoodeth:pltr'],
    Networks.main.hoodeth,
  ),
];""")


class FakeResp:
    def __init__(self, payload):
        self.payload = payload
        self.status_code = 200
        self.text = payload if isinstance(payload, str) else json.dumps(payload)

    def json(self):
        return self.payload if not isinstance(self.payload, str) else json.loads(self.payload)


class FakeSession:
    """Routes GET/POST by URL substring to a payload (or a callable returning one)."""

    def __init__(self, routes):
        self.routes = routes
        self.headers = {}
        self.calls = []

    def request(self, method, url, **kw):
        self.calls.append((method, url, kw))
        for k, v in self.routes.items():
            if k in url:
                return FakeResp(v(kw) if callable(v) else v)
        raise AssertionError(f"unrouted {url}")


class FakeRPC:
    def __init__(self, head=1000, logs_in=(), logs_out=(), meta=None, balances=None, tx_from=None,
                 max_range=None):
        self.head, self.logs_in, self.logs_out = head, list(logs_in), list(logs_out)
        self.meta = meta or {}
        self.balances = balances or {}
        self.tx_from = tx_from or {}
        self.max_range = max_range
        self.log_calls = []

    def call(self, method, params):
        from radar.watchers.onchain import RPCError
        if method == "eth_blockNumber":
            return hex(self.head)
        if method == "eth_getLogs":
            f = params[0]
            frm, to = int(f["fromBlock"], 16), int(f["toBlock"], 16)
            self.log_calls.append((frm, to))
            if self.max_range and to - frm + 1 > self.max_range:
                raise RPCError(f"block range greater than {self.max_range} max")
            return [lg for lg in self.logs_in + self.logs_out
                    if frm <= int(lg["blockNumber"], 16) <= to and _topics_match(f["topics"], lg["topics"])]
        if method == "eth_call":
            to, data = params[0]["to"], params[0]["data"]
            sel = data[:10]
            m = self.meta.get(to, {})
            if sel == "0x95d89b41":
                return _abi_str(m.get("symbol", ""))
            if sel == "0x06fdde03":
                return _abi_str(m.get("name", ""))
            if sel == "0x313ce567":
                return hex(m.get("decimals", 18))
            if sel == "0x70a08231":
                holder = "0x" + data[-40:]
                return hex(self.balances.get((to, holder), 0))
        if method == "eth_getTransactionByHash":
            return {"from": self.tx_from.get(params[0], "0x" + "9" * 40)}
        raise AssertionError(method)


def _topics_match(want, have):
    for i, w in enumerate(want):
        if w is None:
            continue
        if i >= len(have) or have[i] not in (w if isinstance(w, list) else [w]):
            return False
    return True


def _abi_str(s: str) -> str:
    b = s.encode()
    return "0x" + (32).to_bytes(32, "big").hex() + len(b).to_bytes(32, "big").hex() + b.ljust(32, b"\0").hex()


def _log(token, frm, to, value, block, tx="0xabc"):
    return {"address": token, "topics": [TRANSFER, _topic(frm), _topic(to)], "data": hex(value),
            "blockNumber": hex(block), "transactionHash": tx}


@pytest.fixture
def store(tmp_path):
    return Store(str(tmp_path / "t.db"))


# ---------------------------------------------------------------- extraction
def test_extract_bitgo_layout():
    toks = extract_tokens(BITGO_AFTER)
    assert toks["hoodeth:cashcat"] == {"chain": "robinhood", "symbol": "CASHCAT", "name": "Cash Cat",
                                       "address": CASHCAT}
    assert toks["hoodeth:nvda"]["name"] == "NVIDIA Corporation • Robinhood"


def test_extract_enum_then_definition_merges():
    text = "  'baseeth:foo' = 'baseeth:foo',\n" + BITGO_AFTER.replace("hoodeth:cashcat", "baseeth:foo")
    assert extract_tokens(text)["baseeth:foo"]["address"] == CASHCAT


def test_net_added_ignores_moved_lines():
    patch = "--- a/x\n+++ b/x\n-    'eth:old',\n+    'eth:new',\n+    'eth:old',\n"
    assert net_added_lines(patch) == ["    'eth:new',"]


# ---------------------------------------------------------------- code watchers
def test_file_watcher_baseline_then_new_token(store):
    content = {"text": BITGO_BEFORE}
    sess = FakeSession({"raw.githubusercontent.com": lambda kw: content["text"]})
    w = FileSnapshotWatcher("bitgo", "BitGo/BitGoJS", "master", ["hoodethTokens.ts"], sess=sess,
                            downweight=[{"pattern": "• Robinhood$", "factor": 0.25, "reason": "stock"}])
    assert w.poll(store) == []           # baseline
    content["text"] = BITGO_AFTER
    sigs = {s.symbol: s for s in w.poll(store)}
    assert set(sigs) == {"CASHCAT", "PLTR"}
    assert sigs["CASHCAT"].weight == 4 and sigs["CASHCAT"].address == CASHCAT
    assert sigs["PLTR"].weight == 1 and sigs["PLTR"].detail["downweighted"] == "stock"
    assert w.poll(store) == []           # no repeat


def test_file_watcher_chain_filter(store):
    content = {"text": BITGO_BEFORE}
    sess = FakeSession({"raw.githubusercontent.com": lambda kw: content["text"]})
    w = FileSnapshotWatcher("bitgo", "r", "m", ["f"], chains=["base"], sess=sess)
    w.poll(store)
    content["text"] = BITGO_AFTER
    assert w.poll(store) == []


def test_commit_watcher_trustwallet_style(store):
    addr = "0x" + "ab" * 20
    commits = [{"sha": "old"}]
    sess = FakeSession({
        "/commits/new": {"sha": "new", "html_url": "u", "commit": {"message": "Add token"}, "files": [
            {"filename": f"blockchains/base/assets/{addr}/info.json", "status": "added",
             "patch": '+{\n+  "symbol": "CAT",\n+  "description": "see thinking and link"\n+}'},
            {"filename": "blockchains/solana/assets/x/info.json", "status": "added", "patch": "+x"},
        ]},
        "/commits": lambda kw: commits,
    })
    w = CommitWatcher("tw", "trustwallet/assets", "master", path_chains={"blockchains/base/": "base"},
                      keywords=["ink"], sess=sess)
    assert w.poll(store) == []
    commits.insert(0, {"sha": "new"})
    sigs = w.poll(store)
    assert len(sigs) == 1  # "thinking"/"link" must not match keyword "ink"
    assert sigs[0].address == addr and sigs[0].chain == "base"
    assert w.poll(store) == []


# ---------------------------------------------------------------- exchanges
def _rh(pairs):
    return {"results": [{"asset_currency": {"code": c, "name": n}, "display_symbol": f"{c}-USD",
                         "tradability": t, "display_only": t != "tradable"} for c, n, t in pairs]}


def test_robinhood_new_and_tradable(store):
    data = {"v": _rh([("BTC", "Bitcoin", "tradable")])}
    w = RobinhoodWatcher("robinhood", sess=FakeSession({"nummus": lambda kw: data["v"]}))
    assert w.poll(store) == []
    data["v"] = _rh([("BTC", "Bitcoin", "tradable"), ("CASHCAT", "Cash Cat", "untradable")])
    [s] = w.poll(store)
    assert s.symbol == "CASHCAT" and "not tradable yet" in s.title
    data["v"] = _rh([("BTC", "Bitcoin", "tradable"), ("CASHCAT", "Cash Cat", "tradable")])
    [s] = w.poll(store)
    assert "TRADABLE" in s.title


def test_coinbase_new_currency_carries_base_contract(store):
    data = {"v": []}
    w = CoinbaseCurrenciesWatcher("coinbase", chains=["base", "ethereum"],
                                  sess=FakeSession({"coinbase": lambda kw: data["v"]}))
    w.poll(store)
    data["v"] = [{"id": "CAT", "name": "Cat", "status": "online", "supported_networks": [
        {"id": "base", "contract_address": "0xABCDEFabcdefABCDEFabcdefABCDEFabcdefABCD"},
        {"id": "solana", "contract_address": "So1"}]}]
    [s] = w.poll(store)
    assert s.chain == "base" and s.address == "0xabcdefabcdefabcdefabcdefabcdefabcdefabcd"


# ---------------------------------------------------------------- onchain
def _onchain(rpc, wallets=None, **kw):
    wallets = wallets or [{"label": "Wintermute", "address": MM, "kind": "market_maker"},
                          {"label": "Robinhood hot", "address": EXCH, "kind": "exchange"}]
    return OnchainWatcher("robinhood", "", wallets, rpc=rpc, confirmations=0, lookback_blocks=100, **kw)


def test_onchain_warmup_silent_then_first_seen(store):
    spam = "0x" + "5" * 40
    rpc = FakeRPC(head=1000, logs_in=[_log(CASHCAT, "0x" + "7" * 40, MM, 10**18, 950)],
                  meta={CASHCAT: {"symbol": "CASHCAT", "name": "Cash Cat", "decimals": 18},
                        spam: {"symbol": "Visit cat-airdrop.com", "name": "x"}})
    w = _onchain(rpc)
    assert w.poll(store) == []           # warmup marks seen, no alerts
    rpc.head = 1010
    rpc.logs_in += [
        _log(CASHCAT, "0x" + "8" * 40, MM, 5 * 10**18, 1005),   # repeat token: not new
        _log(spam, "0x" + "8" * 40, MM, 10**18, 1006),          # spam name
        _log(CASHCAT, "0x" + "8" * 40, EXCH, 0, 1007),          # zero-value poisoning
        _log(CASHCAT, MM, EXCH, 2_500_000 * 10**18, 1008, tx="0xfeed"),
    ]
    rpc.tx_from["0xfeed"] = MM
    sigs = w.poll(store)
    titles = sorted(s.title for s in sigs)
    assert len(sigs) == 2, titles
    out = next(s for s in sigs if s.detail["direction"] == "out")
    inc = next(s for s in sigs if s.detail["direction"] == "in")
    assert out.detail["verified_sender"] and out.weight == 4.0
    assert "to Robinhood hot" in out.title
    assert inc.detail["wallet_label"] == "Robinhood hot" and "2.5e+06" in inc.title


def test_onchain_shrinks_range_on_provider_limit(store):
    rpc = FakeRPC(head=5000, max_range=300)
    w = _onchain(rpc, max_block_range=1000)
    store.put("cursor:robinhood", "block", 1000)
    w.poll(store)
    assert all(t - f + 1 <= 300 for f, t in rpc.log_calls[-4:])
    assert store.get("cursor:robinhood", "block") == 5000


def test_holdings_check(store):
    rpc = FakeRPC(meta={CASHCAT: {"symbol": "CASHCAT", "decimals": 18}},
                  balances={(CASHCAT, MM): 3 * 10**24})
    [s] = _onchain(rpc).check_holdings(store, CASHCAT)
    assert "Wintermute already holds 3e+06 CASHCAT" in s.title
    assert _onchain(rpc).check_holdings(store, CASHCAT) == []   # once per token


# ---------------------------------------------------------------- correlation + engine
def test_correlation_escalates_across_kinds(store):
    code = store.add_signal(Signal("bitgo", CODE, "bitgo adds cashcat", 4, "robinhood", "CASHCAT", CASHCAT))
    assert assess(store, code).severity == "medium"
    onc = store.add_signal(Signal("onchain:robinhood", ONCHAIN, "MM holds", 3, "robinhood", "CASHCAT", CASHCAT))
    a = assess(store, onc)
    assert a.kinds == {CODE, ONCHAIN} and a.score == 9 and a.severity == "high"
    assert "corroborated" in format_alert(a)


def test_common_symbols_do_not_correlate(store):
    store.add_signal(Signal("bitgo", CODE, "x", 4, "ink", "USDC", "0x" + "1" * 40))
    s = store.add_signal(Signal("kraken", EXCHANGE, "y", 4, None, "USDC"))
    assert len(assess(store, s).related) == 1


class ListAlerter:
    def __init__(self):
        self.sent = []

    def send(self, a):
        self.sent.append(a)


class StubWatcher:
    def __init__(self, name, sigs):
        self.name, self.interval, self.sigs = name, 60, sigs

    def poll(self, store):
        out, self.sigs = self.sigs, []
        return out


def test_engine_runs_holdings_followup(store):
    rpc = FakeRPC(meta={CASHCAT: {"symbol": "CASHCAT", "decimals": 18}}, balances={(CASHCAT, MM): 10**24})
    onc = _onchain(rpc)
    code = StubWatcher("bitgo", [Signal("bitgo", CODE, "bitgo adds hoodeth:cashcat", 4, "robinhood",
                                        "CASHCAT", CASHCAT)])
    alerts = ListAlerter()
    eng = Engine({"db": ":memory:"}, store=store, alerter=alerts, watchers=[code], onchain={"robinhood": onc})
    res = eng.run_due(now=0)
    assert [a.severity for a in res] == ["medium", "high"]
    assert len(alerts.sent) == 2


def test_engine_survives_failing_watcher(store):
    class Boom(StubWatcher):
        def poll(self, store):
            raise RuntimeError("down")
    ok = StubWatcher("ok", [Signal("ok", EXCHANGE, "t", 1, symbol="ZZZ")])
    eng = Engine({"db": ":memory:"}, store=store, alerter=ListAlerter(), watchers=[Boom("b", []), ok])
    assert len(eng.run_due(now=0)) == 1
