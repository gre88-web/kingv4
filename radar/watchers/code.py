"""Watch public source code for newly added token support.

Two modes:

* ``files``: fetch specific files from raw.githubusercontent.com (no API token or rate
  limit), extract the full set of token definitions, and diff it against the previous
  snapshot. Moving or reordering definitions is not reported, only token ids that are
  genuinely new. This is the mode for big generated token lists like BitGo's statics.
* ``commits``: walk new commits through the GitHub API and look at what each one
  adds: chain-prefixed token ids, new files under watched paths whose names contain a
  contract address (Trust Wallet's ``blockchains/<chain>/assets/<address>/``), and
  keyword hits. Set ``GITHUB_TOKEN`` for 5000 req/h instead of 60.
"""
from __future__ import annotations

import logging
import os
import re
from typing import Any

from .. import http
from ..extract import ADDRESS_RE, DEFAULT_ID_PATTERN, DEFAULT_PREFIX_CHAINS, extract_tokens, net_added_lines
from ..models import CODE, Signal
from ..store import Store
from .base import Watcher

log = logging.getLogger(__name__)

RAW = "https://raw.githubusercontent.com/{repo}/{branch}/{path}"
API = "https://api.github.com"


def _weight(base: float, name: str | None, downweight: list[dict[str, Any]]) -> tuple[float, str | None]:
    for rule in downweight:
        if name and re.search(rule["pattern"], name):
            return base * float(rule.get("factor", 0.25)), rule.get("reason", rule["pattern"])
    return base, None


class FileSnapshotWatcher(Watcher):
    kind = CODE

    def __init__(self, name: str, repo: str, branch: str, paths: list[str], *,
                 chains: list[str] | None = None, weight: float = 4.0,
                 id_pattern: str = DEFAULT_ID_PATTERN, prefix_chains: dict[str, str] | None = None,
                 downweight: list[dict[str, Any]] | None = None, bulk_threshold: int = 15,
                 bulk_factor: float = 0.5, interval: float = 300, sess=None) -> None:
        super().__init__(name, interval)
        self.repo, self.branch, self.paths = repo, branch, paths
        self.chains = set(chains) if chains else None
        self.weight = weight
        self.id_pattern = id_pattern
        self.prefix_chains = prefix_chains or DEFAULT_PREFIX_CHAINS
        self.downweight = downweight or []
        self.bulk_threshold, self.bulk_factor = bulk_threshold, bulk_factor
        self.sess = sess or http.session()

    def fetch(self) -> dict[str, dict[str, Any]]:
        tokens: dict[str, dict[str, Any]] = {}
        for path in self.paths:
            url = RAW.format(repo=self.repo, branch=self.branch, path=path)
            text = http.request(self.sess, "GET", url, timeout=60).text
            for tid, info in extract_tokens(text, self.id_pattern, self.prefix_chains).items():
                cur = tokens.setdefault(tid, {**info, "path": path})
                for k in ("name", "address"):
                    if not cur.get(k) and info.get(k):
                        cur[k] = info[k]
                        cur["path"] = path
        return tokens

    def poll(self, store: Store) -> list[Signal]:
        # Any failed file aborts the cycle: a partial snapshot would make tokens look removed
        # and then "new" again on the next good fetch.
        current = self.fetch()
        ns = f"code:{self.name}"
        previous = store.get(ns, "tokens")
        store.put(ns, "tokens", current)
        if previous is None:
            log.info("%s: baseline of %d tokens", self.name, len(current))
            return []

        new = [t for t in sorted(set(current) - set(previous))
               if not self.chains or current[t].get("chain") in self.chains]
        # Dozens of tokens on one chain in one go is a batch onboarding (e.g. tokenized stocks),
        # not a hand-picked listing.
        per_chain: dict[str | None, int] = {}
        for t in new:
            per_chain[current[t].get("chain")] = per_chain.get(current[t].get("chain"), 0) + 1

        signals = []
        for tid in new:
            info = current[tid]
            w, why = _weight(self.weight, info.get("name"), self.downweight)
            if per_chain[info.get("chain")] > self.bulk_threshold:
                w *= self.bulk_factor
                why = ", ".join(x for x in (why, f"bulk add ({per_chain[info.get('chain')]} tokens)") if x)
            title = f"{self.repo}: new token {tid}" + (f" ({info['name']})" if info.get("name") else "")
            signals.append(Signal(
                source=self.name, kind=CODE, title=title, weight=w,
                chain=info.get("chain"), symbol=info.get("symbol"), address=info.get("address"),
                detail={"token_id": tid, "name": info.get("name"), "repo": self.repo, "path": info.get("path"),
                        "url": f"https://github.com/{self.repo}/blob/{self.branch}/{info.get('path')}",
                        **({"downweighted": why} if why else {})},
            ))
        return signals


class CommitWatcher(Watcher):
    kind = CODE

    def __init__(self, name: str, repo: str, branch: str, *,
                 path_chains: dict[str, str] | None = None, keywords: list[str] | None = None,
                 chains: list[str] | None = None, weight: float = 3.0,
                 id_pattern: str = DEFAULT_ID_PATTERN, prefix_chains: dict[str, str] | None = None,
                 max_commits: int = 30, interval: float = 600, sess=None) -> None:
        super().__init__(name, interval)
        self.repo, self.branch = repo, branch
        self.path_chains = path_chains or {}
        # Whole-word, case-insensitive: "ink" must not match "link".
        self.keywords = [(k, re.compile(rf"(?<![A-Za-z0-9]){re.escape(k)}(?![A-Za-z0-9])", re.I))
                         for k in (keywords or [])]
        self.chains = set(chains) if chains else None
        self.weight = weight
        self.id_pattern = id_pattern
        self.prefix_chains = prefix_chains or DEFAULT_PREFIX_CHAINS
        self.max_commits = max_commits
        self.sess = sess or http.session()
        token = os.environ.get("GITHUB_TOKEN")
        self.headers = {"Accept": "application/vnd.github+json"}
        if token:
            self.headers["Authorization"] = f"Bearer {token}"

    def _get(self, path: str, **params: Any) -> Any:
        return http.request(self.sess, "GET", f"{API}{path}", headers=self.headers, params=params).json()

    def poll(self, store: Store) -> list[Signal]:
        ns = f"commits:{self.name}"
        commits = self._get(f"/repos/{self.repo}/commits", sha=self.branch, per_page=self.max_commits)
        if store.get(ns, "baselined") is None:
            for c in commits:
                store.mark_seen(ns, c["sha"])
            store.put(ns, "baselined", True)
            log.info("%s: baseline at %s", self.name, commits[0]["sha"][:10] if commits else "empty repo")
            return []

        signals: list[Signal] = []
        for c in reversed(commits):  # oldest first
            if store.is_seen(ns, c["sha"]):
                continue
            full = self._get(f"/repos/{self.repo}/commits/{c['sha']}")
            signals.extend(self._scan_commit(store, full))
            store.mark_seen(ns, c["sha"])
        return signals

    def _chain_for_path(self, filename: str) -> str | None:
        for prefix, chain in self.path_chains.items():
            if filename.startswith(prefix):
                return chain
        return None

    def _scan_commit(self, store: Store, commit: dict[str, Any]) -> list[Signal]:
        sha = commit["sha"]
        url = commit.get("html_url") or f"https://github.com/{self.repo}/commit/{sha}"
        msg = (commit.get("commit", {}).get("message") or "").splitlines()[0][:120]
        found: dict[str, Signal] = {}

        def emit(key: str, s: Signal) -> None:
            if self.chains and s.chain and s.chain not in self.chains:
                return
            if key not in found and store.mark_seen(f"commit-tokens:{self.name}", key):
                found[key] = s

        for f in commit.get("files", []):
            fn = f.get("filename", "")
            path_chain = self._chain_for_path(fn)
            if self.path_chains and path_chain is None:
                continue
            base_detail = {"repo": self.repo, "commit": sha, "url": url, "message": msg, "file": fn}

            # 1. New file whose path names a contract address (Trust Wallet style).
            if f.get("status") == "added" and path_chain:
                a = ADDRESS_RE.search(fn)
                if a:
                    addr = a.group(0).lower()
                    emit(f"{path_chain}:{addr}", Signal(
                        source=self.name, kind=CODE, weight=self.weight, chain=path_chain, address=addr,
                        title=f"{self.repo}: new asset {addr} on {path_chain}", detail=base_detail))

            added = net_added_lines(f.get("patch") or "")
            if not added:
                continue
            text = "\n".join(added)

            # 2. Chain-prefixed token ids in genuinely added lines.
            for tid, info in extract_tokens(text, self.id_pattern, self.prefix_chains).items():
                emit(tid, Signal(
                    source=self.name, kind=CODE, weight=self.weight, chain=info["chain"],
                    symbol=info["symbol"], address=info["address"],
                    title=f"{self.repo}: adds {tid}" + (f" ({info['name']})" if info.get("name") else ""),
                    detail={**base_detail, "token_id": tid, "name": info.get("name")}))

            # 3. Keyword hits: weaker, no token identity unless an address is on the line.
            for line in added:
                hit = next((k for k, rx in self.keywords if rx.search(line)), None)
                if not hit:
                    continue
                a = ADDRESS_RE.search(line)
                key = f"kw:{hit}:{a.group(0).lower() if a else line.strip()[:80]}"
                emit(key, Signal(
                    source=self.name, kind=CODE, weight=self.weight * 0.5, chain=path_chain,
                    address=a.group(0).lower() if a else None,
                    title=f"{self.repo}: '{hit}' in {fn}",
                    detail={**base_detail, "line": line.strip()[:200]}))
        return list(found.values())
