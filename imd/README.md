# IMD prompts for Kekborn

Paste each `.txt` file as-is into the IMD field below. Every file is under 3,000
characters, so each one fits any IMD objective field.

| Step | File | Where | Chars | IMD limit |
|---|---|---|---|---|
| 1 | `1-goal-genesis.txt` | Goal objective (research-only goal) | 2,133 | 3,000 |
| 2 | `2-art-style-lock.txt` | Job objective (image / build job) | 2,246 | 8,000 |
| 3 | `3-website-approval-and-prototype.txt` | Website job objective | 2,210 | 8,000 |
| 4 | `4-company-mint-after-approval.txt` | Company (launch) objective, **only after you approve all art** | 1,624 | 8,000 |

Order and gates:

1. **Snapshot** → you review `scores.csv` and the data-accessibility report.
2. **Art style lock** → you review the 12 sample portraits and the contact sheet. Only
   continue when the style looks right; otherwise rerun step 2 with your feedback.
3. **Dashboard + prototype** (attach `scores.csv` and the approved layer library and
   compositor as inputs) → you approve every Kekborn and sign the approval manifest.
4. **Launch** the contract and claim site.

## How the long spec reaches the agents

IMD does not let you upload your own skill: the `skill` field only takes IDs from IMD's
built-in catalog, and Goals have no skill or file field at all. So the full spec lives in
this repo, in `spec/`, and each prompt:

- writes its own concrete steps (IMD refuses work that is just "go read this URL and do
  what it says": `remote_instructions`), and
- names the spec as the requirements source to implement against, pinned to commit
  `0325909ca3f6dbabfad6c90f1bc68ed068df304e` (plus a sha256 for the Genesis file), so the
  agents read exactly the version you wrote.

The repository must be **public** for IMD agents to read it. If you edit the spec, commit,
then update the commit hash (and sha256) in the prompts.

## Approval gate

Nothing in steps 1–3 deploys, mints or spends. Step 4 deploys a contract, so only start it
after you have approved every Kekborn in the dashboard and signed the approval manifest.
