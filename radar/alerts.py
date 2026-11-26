from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

from . import http
from .correlate import Assessment

log = logging.getLogger(__name__)

ICON = {"low": "·", "medium": "▲", "high": "🚨"}


def format_alert(a: Assessment) -> str:
    s = a.signal
    lines = [f"{ICON[a.severity]} [{a.severity.upper()} {a.score:g}] {s.title}"]
    ident = " ".join(x for x in (s.symbol, s.chain, s.address) if x)
    if ident:
        lines.append(f"   token: {ident}")
    url = s.detail.get("url") or (s.detail.get("tx") and _tx_url(s.chain, s.detail["tx"]))
    if url:
        lines.append(f"   {url}")
    others = [r for r in a.related if r.id != s.id]
    if others:
        lines.append(f"   corroborated by {len(a.sources) - 1} other source(s), kinds: {', '.join(sorted(a.kinds))}")
        for r in sorted(others, key=lambda r: r.ts)[-5:]:
            when = datetime.fromtimestamp(r.ts, timezone.utc).strftime("%Y-%m-%d %H:%M")
            lines.append(f"     - {when}Z {r.title}")
    return "\n".join(lines)


EXPLORERS = {
    "ethereum": "https://etherscan.io/tx/",
    "base": "https://basescan.org/tx/",
    "ink": "https://explorer.inkonchain.com/tx/",
    "robinhood": "https://robinhoodchain.blockscout.com/tx/",
}


def _tx_url(chain: str | None, tx: str) -> str | None:
    base = EXPLORERS.get(chain or "")
    return base + tx if base else None


class Alerter:
    """Console always; Telegram and/or Discord when their env vars are set."""

    def __init__(self) -> None:
        self.sess = http.session()
        self.tg_token = os.environ.get("TELEGRAM_BOT_TOKEN")
        self.tg_chat = os.environ.get("TELEGRAM_CHAT_ID")
        self.discord = os.environ.get("DISCORD_WEBHOOK_URL")

    def send(self, a: Assessment) -> None:
        text = format_alert(a)
        print(text, flush=True)
        try:
            if self.tg_token and self.tg_chat:
                http.request(self.sess, "POST", f"https://api.telegram.org/bot{self.tg_token}/sendMessage",
                             json={"chat_id": self.tg_chat, "text": text, "disable_web_page_preview": True},
                             retries=2)
            if self.discord:
                http.request(self.sess, "POST", self.discord, json={"content": text[:1900]}, retries=2)
        except http.HttpError as e:
            log.warning("alert delivery failed: %s", e)
