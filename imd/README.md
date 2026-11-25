# IMD prompts for PEPEVERSE

Paste each `.txt` file as-is into the IMD field below. Every file is under 3,000
characters, so each one fits any IMD objective field.

| File | Where | Chars | IMD limit |
|---|---|---|---|
| `1-goal-genesis.txt` | Goal objective (research-only goal) | 2,135 | 3,000 |
| `2-website-approval-and-prototype.txt` | Website job objective | 2,043 | 8,000 |
| `3-company-mint-after-approval.txt` | Company (launch) objective, **only after you approve the art** | 1,502 | 8,000 |

Run them in order: 1 → review the snapshot → 2 (feed it `scores.csv`) → approve art in
the dashboard → 3.

## How the long spec reaches the agents

IMD does not let you upload your own skill: the `skill` field only takes IDs from IMD's
built-in catalog, and Goals have no skill or file field at all. So the full spec lives in
this repo, in `spec/`, and each prompt:

- writes its own concrete steps (IMD refuses work that is just "go read this URL and do
  what it says": `remote_instructions`), and
- names the spec as the requirements source to implement against, pinned to commit
  `cbef28ee95096562e90693b0b9aeb169ed19d29e` (plus a sha256 for the Genesis file), so the
  agents read exactly the version you wrote.

The repository must be **public** for IMD agents to read it. If you edit the spec, commit,
then update the commit hash (and sha256) in the prompts.

## Approval gate

Nothing in prompts 1 and 2 deploys, mints or spends. Prompt 3 deploys a contract, so only
start it after you have approved every Pepe in the dashboard and signed the approval
manifest.
