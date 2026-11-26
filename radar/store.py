from __future__ import annotations

import json
import sqlite3
import time
from typing import Any, Iterable

from .models import Signal

SCHEMA = """
CREATE TABLE IF NOT EXISTS kv (
    ns TEXT NOT NULL, key TEXT NOT NULL, value TEXT NOT NULL,
    updated REAL NOT NULL, PRIMARY KEY (ns, key)
);
CREATE TABLE IF NOT EXISTS seen (
    ns TEXT NOT NULL, item TEXT NOT NULL, first_ts REAL NOT NULL,
    PRIMARY KEY (ns, item)
);
CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL, source TEXT NOT NULL, kind TEXT NOT NULL,
    chain TEXT, symbol TEXT, address TEXT,
    title TEXT NOT NULL, weight REAL NOT NULL, detail TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS signals_symbol ON signals(symbol);
CREATE INDEX IF NOT EXISTS signals_address ON signals(address);
CREATE INDEX IF NOT EXISTS signals_ts ON signals(ts);
"""


class Store:
    """SQLite-backed state: snapshots/cursors (kv), first-seen sets (seen), and emitted signals."""

    def __init__(self, path: str = "radar.db") -> None:
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)

    # ---- kv -------------------------------------------------------------
    def get(self, ns: str, key: str, default: Any = None) -> Any:
        row = self.db.execute("SELECT value FROM kv WHERE ns=? AND key=?", (ns, key)).fetchone()
        return json.loads(row["value"]) if row else default

    def put(self, ns: str, key: str, value: Any) -> None:
        self.db.execute(
            "INSERT INTO kv(ns,key,value,updated) VALUES(?,?,?,?) "
            "ON CONFLICT(ns,key) DO UPDATE SET value=excluded.value, updated=excluded.updated",
            (ns, key, json.dumps(value, sort_keys=True), time.time()),
        )
        self.db.commit()

    def scan(self, ns_prefix: str, key: str) -> list[tuple[str, Any]]:
        """All (ns, value) rows whose ns starts with ns_prefix and whose key equals key."""
        rows = self.db.execute("SELECT ns, value FROM kv WHERE ns LIKE ? AND key = ?",
                               (ns_prefix + "%", key)).fetchall()
        return [(r["ns"], json.loads(r["value"])) for r in rows]

    # ---- seen -----------------------------------------------------------
    def mark_seen(self, ns: str, item: str) -> bool:
        """Record item; return True if it was not seen before."""
        cur = self.db.execute(
            "INSERT OR IGNORE INTO seen(ns,item,first_ts) VALUES(?,?,?)", (ns, item, time.time())
        )
        self.db.commit()
        return cur.rowcount == 1

    def is_seen(self, ns: str, item: str) -> bool:
        return self.db.execute("SELECT 1 FROM seen WHERE ns=? AND item=?", (ns, item)).fetchone() is not None

    # ---- signals --------------------------------------------------------
    def add_signal(self, s: Signal) -> Signal:
        cur = self.db.execute(
            "INSERT INTO signals(ts,source,kind,chain,symbol,address,title,weight,detail) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            (s.ts, s.source, s.kind, s.chain, s.symbol, s.address, s.title, s.weight,
             json.dumps(s.detail, sort_keys=True, default=str)),
        )
        self.db.commit()
        s.id = cur.lastrowid
        return s

    def related(self, s: Signal, since: float, ignore_symbols: Iterable[str] = ()) -> list[Signal]:
        """Signals (including s) that refer to the same token by address or by symbol."""
        clauses, args = [], []
        if s.address:
            clauses.append("address = ?")
            args.append(s.address)
        if s.symbol and s.symbol not in set(ignore_symbols):
            clauses.append("symbol = ?")
            args.append(s.symbol)
        if not clauses:
            return [s]
        rows = self.db.execute(
            f"SELECT * FROM signals WHERE ts >= ? AND ({' OR '.join(clauses)}) ORDER BY ts",
            [since, *args],
        ).fetchall()
        out = [self._row(r) for r in rows]
        if s.id is not None and all(o.id != s.id for o in out):
            out.append(s)
        return out

    def recent(self, limit: int = 50, since: float = 0.0) -> list[Signal]:
        rows = self.db.execute(
            "SELECT * FROM signals WHERE ts >= ? ORDER BY ts DESC LIMIT ?", (since, limit)
        ).fetchall()
        return [self._row(r) for r in rows]

    @staticmethod
    def _row(r: sqlite3.Row) -> Signal:
        return Signal(
            id=r["id"], ts=r["ts"], source=r["source"], kind=r["kind"], chain=r["chain"],
            symbol=r["symbol"], address=r["address"], title=r["title"], weight=r["weight"],
            detail=json.loads(r["detail"]),
        )
