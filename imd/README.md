# IMD prompts for Kekborn

Paste each `.txt` file as-is into the IMD field below. Every file is under 3,000
characters, so each one fits any IMD objective field.

| Step | File | Where | Chars | IMD limit |
|---|---|---|---|---|
| 1 | `1-goal-genesis.txt` | Goal objective (research-only goal) | 2,367 | 3,000 |
| 2 | `2-art-style-lock.txt` | Job objective (image / build job) | 2,285 | 8,000 |
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
this repo, in `spec/`.

- **Step 1 (Goal) is self-contained:** it carries every rule it needs and pins no file.
  IMD screens a pinned file like the objective itself, and earlier versions were refused
  because the spec's wording read as a request for verbatim command output.
- **Steps 2–4** each write their own concrete steps (IMD refuses work that is just "go
  read this URL and do what it says": `remote_instructions`) and name the spec as the requirements source to implement against, pinned to commit
  `3f68cbcccaf88ff3fce3f30964ca68f5ade01e18`, so the agents read exactly the version
  you wrote.

The repository must be **public** for IMD agents to read it. If you edit the spec, commit,
then update the commit hash in prompts 2–4.

## Approval gate

Nothing in steps 1–3 deploys, mints or spends. Step 4 deploys a contract, so only start it
after you have approved every Kekborn in the dashboard and signed the approval manifest.
