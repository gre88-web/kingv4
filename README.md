# kingv4: listing radar

Watches public data for the early signs of a token listing on **Ethereum, Base,
Robinhood Chain and Ink**, and alerts when independent sources agree.

It's the "3i" playbook as a program. That group saw BitGo add Cash Cat to Robinhood
Chain on GitHub, watched market-maker wallets fill up, and was positioned before the
listing was announced.

| Source | What it watches | Why it leads |
|---|---|---|
| **Code** | BitGo's token registry (`BitGo/BitGoJS` statics), Trust Wallet assets | Custodians and wallets must support a token before an exchange can list it |
| **Exchange APIs** | Robinhood `currency_pairs`, Coinbase currencies + products, Kraken assets | Assets often appear as *untradable* / *trading disabled* before launch; the flip to tradable is the listing |
| **Onchain** | Labeled wallets (market makers, exchanges, teams) via `eth_getLogs` | Market makers take inventory before a listing |

When a code or exchange signal names a contract address, the radar immediately checks
`balanceOf` on every watched wallet on that chain ("BitGo just added X, and Wintermute
already holds 3M X").

## Does it work? A backtest on BitGo's history

Replaying `BitGo/BitGoJS` from 2026-07-15 through 2026-11-26, Robinhood Chain only.
Stock and ETF tokens and bulk batches are downweighted. Here is every token that would
have alerted at full weight:

```
2026-07-27  d958209f6d  hoodeth:cashcat      Cash Cat         0x020bfc650a365f8bb26819deaabf3e21291018b4
2026-08-31  8ff8cd925a  hoodeth:pons         Pons             0x39dbed3a2bd333467115de45665cc57f813c4571
2026-08-31  8ff8cd925a  hoodeth:stonkbroker  StonkBroker      0xe934e36a439c94017b64a3fece66af12099abf50
2026-09-16  df1605b924  hoodeth:ai           Artificial Inu   ...  (+ goose, index, pipedog, ram, tendies, up)
2026-10-08  6a7f49b978  hoodeth:orbio        Orbio            0xaa07a0e9209e16ac99708c3ec70159c6ef3128a3
2026-10-30  bd3a04b7df  hoodeth:ansemcat     Ansem Cat        0x67c51c928d5d8383f3a58fc591a4e6f6463949ed
2026-11-12  c53a53ae38  hoodeth:rlusd        Ripple USD       0x8d58c0c60b8d6b88fa98b291a646db34d0f98258
```

That's 13 alerts in four months, out of several hundred Robinhood Chain tokens BitGo
added. Both the Cash Cat and PONS trades are on the list. Cash Cat appears 10 days before
the Aug 6 listing. As of 2026-11-26, Robinhood's public API lists CASHCAT as tradable,
and PONS, STONKBROKER, AI, INDEX and ORBIO as `untradable`. The exchange watcher alerts
when that state flips.

Run it yourself:

```bash
git clone --filter=blob:none https://github.com/BitGo/BitGoJS.git /tmp/bitgo
python -m radar.backtest /tmp/bitgo --since 2026-07-15 --chains robinhood --full-only
```

## Quickstart

```bash
pip install -e .          # or: pip install requests pyyaml
radar check               # probes every RPC and endpoint
radar run                 # first pass records a baseline silently, then alerts on changes
radar candidates          # tokens ranked by combined evidence
radar signals --days 3    # raw signal log
```

`python -m radar ...` works without installing.

### Setup that matters

1. **Wallets.** Put labeled addresses in `wallets.yaml`, or in `wallets.local.yaml`,
   which is gitignored. Take labels from Arkham, Etherscan, Basescan or Nansen and
   verify them yourself. The onchain watcher does nothing without wallets.
2. **RPCs.** The defaults are free public endpoints and rate-limit quickly, Base
   especially. Get free keys (Alchemy, QuickNode, ...) and set them per chain:
   `RADAR_RPC_ETHEREUM`, `RADAR_RPC_BASE`, `RADAR_RPC_ROBINHOOD`, `RADAR_RPC_INK`.
   Raise `max_block_range` in `config.yaml` when your provider allows it.
3. **GitHub token.** Set `GITHUB_TOKEN` for the Trust Wallet commit watcher (5000 req/h
   instead of 60). The BitGo watcher uses raw.githubusercontent.com and needs none.
4. **Alerts.** Alerts always print to the console. Set `TELEGRAM_BOT_TOKEN` +
   `TELEGRAM_CHAT_ID` and/or `DISCORD_WEBHOOK_URL` to push them too.

## How scoring works

Each signal has a weight:

| Signal | Weight |
|---|---|
| BitGo new token | 4 |
| Stock-like or bulk-added BitGo token | 1–2 |
| Exchange new asset | 4 |
| Exchange asset becomes tradable | 5 |
| Market maker / exchange wallet first-seen | 3 |
| Market maker sent the token, tx signed by the wallet | 4 |

Signals about the same token are matched by contract address or by ticker. Common
tickers such as USDC are ignored. A token's score is the best weight from each source,
plus 2 for every extra *kind* of source.

| Severity | Rule |
|---|---|
| `high` | 2+ kinds and score ≥ 6 (e.g. BitGo add + market maker holding) |
| `medium` | score ≥ 4 |
| `low` | everything else |

Set `alert_min_severity` in `config.yaml` to cut noise.

## Noise controls built in

- Every watcher's first poll is a silent baseline.
- BitGo files are diffed as token *sets*. Their bot rewrites and reorders files, so a
  line-based diff would report hundreds of fake "additions".
- Zero-value transfers are dropped (address poisoning), and so are tokens named like
  spam ("visit ...", URLs, "claim"). A Transfer event "from" a market maker only counts
  as verified when the market maker also signed the transaction, because a spam
  contract can emit fake events.
- RPC range limits are handled automatically: the block range halves until the
  provider accepts it.

## Caveats

- This finds *candidates*, not trades. Many flagged tokens never list, and listings
  often dump on the news. Liquidity on these tokens is thin. Paper-trade first.
- The edge decays once a playbook is public, and signals can be planted as bait.
  Lean on multi-source agreement.
- Only use data that is genuinely public. Information that was leaked, accessed
  without authorization, or obtained from insiders is a different legal category.
  Respect each API's terms and keep polling intervals polite.

## Layout

```
radar/
  watchers/code.py       BitGo-style file snapshots + GitHub commit scanning
  watchers/exchange.py   Robinhood / Coinbase / Kraken listing diffs
  watchers/onchain.py    labeled-wallet ERC-20 flows + holdings check
  correlate.py           cross-source scoring
  engine.py              scheduler, follow-up checks, alerting
  backtest.py            replay a git history through the code watcher
tests/                   pytest suite (no network)
```
