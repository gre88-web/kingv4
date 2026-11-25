# IMD prompts for Kekborn

Paste each `.txt` file as-is into the IMD field below. Every file is under 3,000
characters, so each one fits any IMD objective field.

| Step | File | Where | Chars | IMD limit |
|---|---|---|---|---|
| 1a | `1-goal-genesis.txt` | Goal objective: orchestrated, `researchOnly: true`, workers 50, maxItems 50, maxEpisodes 5 | 2,503 | 3,000 |
| 1b | `1b-job-snapshot-data.txt` | Job objective (code job): builds and runs the snapshot pipeline | 2,835 | 8,000 |
| 2 | `2-art-style-lock.txt` | Goal or job objective: art v2, image-model-painted layers on the existing compositor repo | 2,870 | 8,000 |
| 3 | `3-website-approval-and-prototype.txt` | Website job objective | 2,210 | 8,000 |
| 4 | `4-company-mint-after-approval.txt` | Company (launch) objective, **only after you approve all art** | 1,624 | 8,000 |

Order and gates:

1. **Run 1a, 1b and 2 at the same time.** They do not depend on each other. 1a and 1b use
   the same fixed snapshot time (`2026-11-25T00:00:00Z`, last block at or before it on
   each chain), so their numbers can be cross-checked.
   - 1a (Goal) researches the data and designs the scoring formula and rarity cut points.
   - 1b (job) collects the full dataset as files with a rerunnable script. Its scoring
     weights live in `scoring.json`; once 1a delivers the final formula, put it there and
     rerun the scoring step only.
   - 2 (art) produces the style guide, layer library and 12 sample portraits.
2. **You review:** 1b's `scores.csv` against 1a's methodology, and the 12 sample portraits.
   If the art style is off, rerun 2 with your feedback.
3. **Dashboard + prototype** (attach `scores.csv` and the approved layer library and
   compositor as inputs) → you approve every Kekborn and sign the approval manifest.
4. **Launch** the contract and claim site.

To change the snapshot time, edit it in both 1a and 1b before running them.

## How the long spec reaches the agents

IMD does not let you upload your own skill: the `skill` field only takes IDs from IMD's
built-in catalog, and Goals have no skill or file field at all. So the full spec lives in
this repo, in `spec/`.

- **Steps 1a, 1b and 2 are self-contained:** they carry every rule they need and pin no file.
  IMD screens a pinned file like the objective itself, and earlier versions were refused
  because the spec's wording read as a request for verbatim command output.
- **Steps 3–4** each write their own concrete steps (IMD refuses work that is just "go
  read this URL and do what it says": `remote_instructions`) and name the spec as the requirements source to implement against, pinned to commit
  `3f68cbcccaf88ff3fce3f30964ca68f5ade01e18`, so the agents read exactly the version
  you wrote.

The repository must be **public** for IMD agents to read it. If you edit the spec, commit,
then update the commit hash in prompts 3–4.

## Approval gate

Nothing in steps 1–3 deploys, mints or spends. Step 4 deploys a contract, so only start it
after you have approved every Kekborn in the dashboard and signed the approval manifest.
