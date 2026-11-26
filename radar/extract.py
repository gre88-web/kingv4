"""Pull token definitions out of source files.

Built around how custody/wallet SDKs (BitGo statics and similar) declare tokens: a
chain-prefixed id such as ``'hoodeth:cashcat'`` followed, within a few lines, by a
display name and a contract address. The id pattern and prefix->chain map are
configurable per watcher, so other repos with similar layouts work too.
"""
from __future__ import annotations

import re
from typing import Any

ADDRESS_RE = re.compile(r"0x[a-fA-F0-9]{40}(?![a-fA-F0-9])")
QUOTED_RE = re.compile(r"""['"]([^'"\n]{1,80})['"]""")
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")

DEFAULT_ID_PATTERN = r"""['"]((?:eth|baseeth|hoodeth|inketh):[a-z0-9._-]+)['"]"""
DEFAULT_PREFIX_CHAINS = {"eth": "ethereum", "baseeth": "base", "hoodeth": "robinhood", "inketh": "ink"}


def extract_tokens(
    text: str,
    id_pattern: str = DEFAULT_ID_PATTERN,
    prefix_chains: dict[str, str] | None = None,
    lookahead: int = 8,
) -> dict[str, dict[str, Any]]:
    """Return {token_id: {chain, symbol, name, address}} for every token id found.

    For each id occurrence we scan forward (up to ``lookahead`` lines, stopping at the
    next different id) for the first quoted string (the display name) and the first
    contract address. An id seen several times keeps the first non-empty value of each field,
    so an enum entry without an address is filled in by the real definition later.
    """
    prefix_chains = prefix_chains or DEFAULT_PREFIX_CHAINS
    id_re = re.compile(id_pattern)
    lines = text.splitlines()
    out: dict[str, dict[str, Any]] = {}

    for i, line in enumerate(lines):
        for m in id_re.finditer(line):
            tid = m.group(1)
            prefix, _, sym = tid.partition(":")
            info = out.setdefault(
                tid,
                {"chain": prefix_chains.get(prefix), "symbol": sym.upper() or None, "name": None, "address": None},
            )
            if info["name"] and info["address"]:
                continue
            # Scan the rest of this line, then following lines.
            window = [line[m.end():]] + lines[i + 1 : i + 1 + lookahead]
            for j, chunk in enumerate(window):
                if j > 0:
                    other = [x.group(1) for x in id_re.finditer(chunk)]
                    if any(o != tid for o in other):
                        break
                if info["address"] is None:
                    a = ADDRESS_RE.search(chunk)
                    if a:
                        info["address"] = a.group(0).lower()
                if info["name"] is None:
                    for q in QUOTED_RE.finditer(chunk):
                        val = q.group(1).strip()
                        if id_re.fullmatch(f"'{val}'") or UUID_RE.match(val) or ADDRESS_RE.fullmatch(val):
                            continue
                        info["name"] = val
                        break
                if info["name"] and info["address"]:
                    break
    return out


def net_added_lines(patch: str) -> list[str]:
    """Lines added by a unified diff that were not simply moved (also removed elsewhere)."""
    added, removed = [], set()
    for line in patch.splitlines():
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+"):
            added.append(line[1:])
        elif line.startswith("-"):
            removed.add(line[1:].strip())
    return [a for a in added if a.strip() not in removed]
