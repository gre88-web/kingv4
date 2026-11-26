from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

EXPECTED_CHAIN_IDS = {"ethereum": 1, "base": 8453, "robinhood": 4663, "ink": 57073}


def load(path: str = "config.yaml") -> dict[str, Any]:
    cfg = yaml.safe_load(Path(path).read_text()) or {}
    base = Path(path).resolve().parent

    # RPC overrides, e.g. RADAR_RPC_BASE=https://base-mainnet.g.alchemy.com/v2/<key>
    for name, chain in (cfg.get("chains") or {}).items():
        env = os.environ.get(f"RADAR_RPC_{name.upper()}")
        if env:
            chain["rpc"] = env

    # Wallet lists: every file listed under wallet_files that exists (later files can add more).
    wallets: list[dict[str, Any]] = []
    for wf in cfg.get("wallet_files", ["wallets.yaml", "wallets.local.yaml"]):
        p = base / wf
        if p.exists():
            wallets.extend((yaml.safe_load(p.read_text()) or {}).get("wallets") or [])
    cfg["wallets"] = [_check_wallet(w) for w in wallets]
    cfg["db"] = str(base / cfg.get("db", "radar.db"))
    return cfg


def _check_wallet(w: dict[str, Any]) -> dict[str, Any]:
    addr = str(w.get("address", ""))
    if not (addr.startswith("0x") and len(addr) == 42):
        raise ValueError(f"bad wallet address {addr!r} for {w.get('label')!r}")
    w["address"] = addr.lower()
    w.setdefault("kind", "other")
    w.setdefault("label", addr[:10])
    return w


def wallets_for(cfg: dict[str, Any], chain: str) -> list[dict[str, Any]]:
    return [w for w in cfg["wallets"] if not w.get("chains") or chain in w["chains"]]
