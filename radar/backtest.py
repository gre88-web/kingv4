"""Replay a local git clone's history through the file-snapshot logic.

Answers "what would the radar have flagged, and when?" for a code watcher, e.g.:

    git clone --filter=blob:none https://github.com/BitGo/BitGoJS.git /tmp/bitgo
    python -m radar.backtest /tmp/bitgo --since 2026-07-01 --chains robinhood

Each commit that touches a watched path is replayed in order; tokens that appear in
the union snapshot for the first time are printed with the commit timestamp.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from typing import Any, Iterator

from . import config as config_mod
from .extract import DEFAULT_ID_PATTERN, DEFAULT_PREFIX_CHAINS, extract_tokens


def _git(repo: str, *args: str) -> str:
    return subprocess.run(["git", "-C", repo, *args], check=True, capture_output=True, text=True).stdout


def replay(repo: str, paths: list[str], since: str, branch: str = "HEAD",
           id_pattern: str = DEFAULT_ID_PATTERN, prefix_chains: dict[str, str] | None = None
           ) -> Iterator[tuple[str, str, str, str, dict[str, Any]]]:
    """Yield (commit_date, sha, subject, token_id, info) for each newly appearing token."""
    log = _git(repo, "log", "--reverse", "--format=%H%x09%aI%x09%s", f"--since={since}", branch, "--", *paths)
    commits = [line.split("\t", 2) for line in log.splitlines() if line]
    if not commits:
        return
    per_path: dict[str, dict[str, dict[str, Any]]] = {}

    def load(sha: str, path: str) -> dict[str, dict[str, Any]]:
        try:
            text = _git(repo, "show", f"{sha}:{path}")
        except subprocess.CalledProcessError:
            return {}
        return extract_tokens(text, id_pattern, prefix_chains or DEFAULT_PREFIX_CHAINS)

    first_parent = f"{commits[0][0]}^"
    for p in paths:
        per_path[p] = load(first_parent, p)
    known = set().union(*per_path.values()) if per_path else set()

    for sha, date, subject in commits:
        changed = set(_git(repo, "diff-tree", "--no-commit-id", "--name-only", "-r", sha, "--", *paths).split())
        for p in changed:
            per_path[p] = load(sha, p)
        merged: dict[str, dict[str, Any]] = {}
        for toks in per_path.values():
            for tid, info in toks.items():
                cur = merged.setdefault(tid, dict(info))
                for k in ("name", "address"):
                    if not cur.get(k) and info.get(k):
                        cur[k] = info[k]
        for tid in sorted(set(merged) - known):
            yield date, sha, subject, tid, merged[tid]
        known |= set(merged)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="radar.backtest")
    ap.add_argument("repo", help="path to a local clone")
    ap.add_argument("--watcher", default="bitgo-statics", help="code watcher name in config.yaml (for paths)")
    ap.add_argument("-c", "--config", default="config.yaml")
    ap.add_argument("--since", default="3 months ago")
    ap.add_argument("--branch", default="HEAD")
    ap.add_argument("--chains", nargs="*", help="only these chains")
    ap.add_argument("--grep", help="only token ids/names matching this regex")
    ap.add_argument("--full-only", action="store_true", help="hide downweighted tokens")
    args = ap.parse_args(argv)

    cfg = config_mod.load(args.config)
    w = next(c for c in cfg.get("code", []) if c["name"] == args.watcher)
    down = [re.compile(d["pattern"]) for d in w.get("downweight") or []]
    rx = re.compile(args.grep, re.I) if args.grep else None
    bulk = int(w.get("bulk_threshold", 15))
    rows = [r for r in replay(args.repo, w["paths"], args.since, args.branch,
                              w.get("id_pattern", DEFAULT_ID_PATTERN), w.get("prefix_chains"))
            if not args.chains or r[4].get("chain") in args.chains]
    per_commit: dict[tuple[str, str | None], int] = {}
    for r in rows:
        per_commit[(r[1], r[4].get("chain"))] = per_commit.get((r[1], r[4].get("chain")), 0) + 1
    n = full = 0
    for date, sha, subject, tid, info in rows:
        if rx and not rx.search(f"{tid} {info.get('name') or ''}"):
            continue
        low = any(d.search(info.get("name") or "") for d in down) or per_commit[(sha, info.get("chain"))] > bulk
        full += not low
        if args.full_only and low:
            continue
        print(f"{date}  {sha[:10]}  {'  ' if low else '* '}{tid:<24} {info.get('name') or '':<40} "
              f"{info.get('address') or ''}  | {subject[:60]}")
        n += 1
    print(f"{n} token(s) shown, {full} at full weight ('*'); others downweighted "
          "(stock-like name or bulk add)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
