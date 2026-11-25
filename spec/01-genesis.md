# 01 — Genesis: Snapshot, Scoring, Rarity, NFTs (Phase 0)

Highest immediate priority. Start the snapshot and NFT generation now, before or in
parallel with game development. Do not wait for the game.

## 1. IMD holder snapshot

Retrieve all available historical holder and wallet activity data and establish:

- Eligible IMD holder wallets.
- IMD balance of each wallet at the snapshot block.
- Historical jobs associated with each wallet.
- Jobs initiated; jobs completed.
- Total IMD spent on jobs.
- Types and categories of jobs.
- Complexity and scope of completed projects.
- Successful deliverables and available quality indicators.
- Other historical contributions to the IMD ecosystem.

Requirements:

- Record the exact snapshot timestamp and block number (per chain).
- Preserve the snapshot in a durable, independently verifiable format (raw source
  responses + derived tables + sha256 of each file; pin to IPFS where appropriate).
- The snapshot is immutable once finalized. Later wallet activity or new jobs never
  change Genesis eligibility or contribution scores.
- Do not treat wallet balance alone as contribution.
- Do not invent missing history or attribute jobs to the wrong wallet.
- If job data cannot be reliably linked to wallets, report exactly what is accessible,
  what is missing and which alternative verification methods exist.

Known data sources to investigate (verify each; do not assume):

- IMD token contracts: Ethereum `0xd34a99bc0f67ae1bbd63c660e6d0b0dd03e263b7`,
  Robinhood chain `0x5f7bb59365ce557c26dbcaa4ee9d39a4b95b7127`. Holders and balances
  at a block come from on-chain reads (Transfer event replay or balanceOf at block);
  the IMD API documents no holders endpoint.
- `GET https://api.imd.fun/requests/paid-by/:address` — orders a wallet paid for
  (max 100, newest first; status, payment, result).
- `GET /jobs/:id` — includes `paidBy`. `GET /jobs/:id/result`, `/report.md`, `/records`.
- `GET /wallets/:address/earnings`, `/seats/owners`, `/seats/:tokenId`, `/seats/records`.
- `GET /goals/:id/*`, `GET /publications`.

## 2. Genesis Contribution Score

Calculate one score per eligible wallet with a transparent, published formula.

Candidate factors:

- Completed jobs.
- Total IMD spent.
- Diversity of job categories.
- Complexity and scope of completed work.
- Successful deliverables and quality indicators.
- Participation in larger multi-agent Goals.
- Other historical ecosystem contributions.

Rules:

- Distinguish completed, abandoned, failed and ongoing jobs.
- No double counting (a goal's child jobs are not counted twice).
- Publish the methodology so holders can recompute their own score.
- The computation is a deterministic script over the frozen snapshot.

## 3. Genesis rarity

Five tiers: Common, Uncommon, Rare, Epic, Legendary.

- Rarity reflects verified historical contribution, not random allocation and not
  balance alone.
- The distribution emerges from the data (e.g. natural breaks in the score
  distribution), not from predetermined percentages.
- Reproducible and independently verifiable.

## 4. Job-specific genetics

Job categories seed initial genetic attributes:

| Job category | Genetic tendency |
|---|---|
| Coding, smart contracts | Problem-solving, technical aptitude |
| Research, reports | Memory, perception, analytical traits |
| Audits | Defence, resilience |
| Websites, products | Creativity, adaptability |
| Oracles, indexers | Perception, information processing |
| Large multi-agent Goals | Possible special genetic combinations |

Genetics drive appearance and may influence gameplay. No pay-to-win: rarity represents
history; long-term success depends on gameplay and adaptation.

## 5. Artwork

Generate unique procedural artwork for every eligible wallet from its score, rarity and
genetics. Consistent identity inspired by Pepe and Spore, with large variation between
creatures. Generation is seeded and deterministic (same inputs + seed = same image), so
an approved image can be reproduced exactly.

Every Genesis Pepe has: unique token ID, unique Genesis identity, intended original
owner wallet, rarity, contribution score, genetic attributes, individual visual
characteristics, initial character traits, personality profile, snapshot reference,
permanent Genesis status.

## 6. Metadata and provenance

Structured metadata per Pepe, created before minting:

- Genesis ID; proposed token ID; intended original wallet.
- Rarity tier; contribution score; contribution categories.
- Genetic attributes; initial character traits; personality profile.
- Snapshot timestamp and block number.
- Original artwork (content hash / IPFS CID).
- Collection identifier: `Kekborn Genesis`.

Original Genesis attributes and traits are never overwritten. Evolution appends new
traits and history. Use decentralized storage where appropriate. The files shown for
approval are byte-for-byte the files that get minted. Never silently change approved
artwork, rarity or genetics.

## 7. Project-owner approval (required before minting)

The project owner (who commissions and pays the IMD swarm) has final creative approval.
Recipients do not approve their own NFTs.

Workflow:

1. Complete the snapshot.
2. Verify eligible wallets.
3. Calculate contribution scores.
4. Determine rarity and genetics.
5. Generate artwork and initial traits.
6. Create and validate metadata.
7. Present the whole collection in a visual approval dashboard.
8. Owner inspects every Pepe: artwork, rarity, score, genetics, traits.
9. Per-NFT approval checkbox/action.
10. Approve the whole collection in one action, or individually.
11. Reject individual designs and request regeneration.
12. Regenerate with a new art seed while keeping rarity, verified genetics and trait
    rules unchanged.
13. After approval: contract deployment, minting and distribution, subject to wallet
    authorization.

Dashboard contents: full preview of every Pepe, recipient wallet, proposed token ID,
rarity, score, genetics, traits and personality, approval checkbox, status, reject and
regenerate, collection-wide overview.

Statuses: `pending`, `approved`, `rejected`, `regeneration_requested`,
`regenerated_awaiting_approval`.

The approval record (who, when, which content hash) is itself stored and signed by the
owner's wallet.

## 8. Minting and distribution (only after approval)

- Prepare and validate the NFT contract (tests + review).
- Obtain explicit deployment authorization from the owner.
- Mint approved NFTs; assign each to its eligible wallet (or a claim contract that
  reserves it for that wallet).
- Verify minting and ownership on-chain.
- Publish the collection and its provenance.
- Unclaimed NFTs stay reserved for their original wallets.
- Never request private keys or seed phrases. All signing happens in the authorized
  wallet. No autonomous spending.
