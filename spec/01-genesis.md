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

- The snapshot has one chosen block per chain; snapshot.json stores each block number
  and its UTC time.
- The snapshot is a durable, independently verifiable dataset: collected records as
  JSON data files (one per source), derived CSV tables, and a manifest.json listing
  every delivered file with its sha256. Pin to IPFS where appropriate.
- The snapshot is immutable once finalized. Later wallet activity or new jobs never
  change Genesis eligibility or contribution scores.
- Do not treat wallet balance alone as contribution.
- Do not invent missing history or attribute jobs to the wrong wallet.
- If job data cannot be reliably linked to wallets, data-accessibility.md documents
  which data is available, which is missing and which alternative verification
  methods exist.

Data sources to evaluate (verify each; do not assume):

| Source | What it provides |
|---|---|
| IMD token contract on Ethereum `0xd34a99bc0f67ae1bbd63c660e6d0b0dd03e263b7` and on Robinhood chain `0x5f7bb59365ce557c26dbcaa4ee9d39a4b95b7127` | Holders and balances at the snapshot block (from Transfer history or balance at block). IMD's API documents no holder list. |
| IMD API, orders paid by a wallet | Orders a wallet paid for (up to 100, newest first) with status and payment |
| IMD API, job records | Job details including the paying wallet, result and records |
| IMD API, wallet earnings and seats | Earnings per wallet; seat owners and their work history |
| IMD API, goals and publications | Goal structure (to avoid double counting) and published deliverables |

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

## 5. Artwork — one style: Tudor court oil portrait

Every Kekborn is a **Renaissance court oil portrait in a frame**, in the manner of a
16th-century Tudor royal portrait: rich brocade, fur, jewels and a patterned backdrop,
like a dynasty portrait hanging in a castle hall. One style for the whole collection;
individuals vary only through trait layers.

Visual reference (owner's choice): the hand-painted look of Pepelangelo's royal Pepe
portraits, e.g. "Pepe as Henry VIII" — real brushwork, dense jewel and embroidery
detail, a frog face full of character. **Reference for quality and feel only:** do not
copy Pepelangelo's paintings or any specific historical painting; use the period style.

### 5.1 Fixed style rules (identical for every token)

- **Subject:** an anthropomorphic frog noble with a **Pepe-like face of its own design**:
  large heavy-lidded eyes with clear irises, a wide mouth with full muted-red lips,
  smooth green skin, very expressive (melancholy, smug, suspicious, dim, regal). It must
  read as its own character, not as Matt Furie's Pepe.
- **Pose and crop:** half-length, three-quarter view facing left, eyes at the same
  height on every portrait. One shared bust template that every layer aligns to.
- **Rendering:** hand-painted oil look — visible brushstrokes and impasto highlights on
  jewels and gold thread, glazed shadows, soft light from the upper left, warm varnish,
  fine craquelure. No flat vector, no code-drawn shapes, no pixel art, no photo realism.
- **Costume:** Tudor court dress — brocade and damask doublets, slashed sleeves, fur
  trim, pearl and gem chains, embroidered collars, velvet hats.
- **Palette:** deep greens, oxblood, black, ochre, cream, gold leaf. Skin colours come
  from a fixed list of painted greens and rare skins.
- **Canvas:** 4:5 portrait, master at 2048×2560 PNG, inside the frame.
- **Background:** dark patterned damask or tapestry, with a heraldic banner in the
  dynasty's colours.

### 5.2 Rarity is shown by the frame and regalia, not a different style

| Tier | Frame | Regalia |
|---|---|---|
| Common | plain dark wood | simple cloth, no headwear or a hood |
| Uncommon | carved oak | brooch, fur collar |
| Rare | silver | chain of office, circlet |
| Epic | gilded gold | crown, rich robes, jewels |
| Legendary | ornate gold with gems and a name plaque | high crown, mantle, faint holy glow |

### 5.3 Genetics are shown by attire and props

| Contribution category | Visual |
|---|---|
| Code, smart contracts | scholar's robe, spectacles, quill |
| Research, reports | monocle, scroll, candle |
| Audits | plate armour, shield on the banner |
| Websites, products | artisan's or painter's garb, brush |
| Oracles, indexers | seer's hood, crystal orb |
| Multi-agent goals | council sash, signet ring, rare combined props |

Personality traits set the facial expression (smug, paranoid side-eye, serene, scowl,
dim grin) and small details (a stolen pastry for Goblin Mode, drool for Professional
Napper, etc.).

### 5.4 Coat of arms

Each Kekborn gets a procedurally generated coat of arms (tincture, division, ordinary,
charge such as a frog, lilypad, crown or fly), rendered in the same painted style on the
banner and as a small shield on the frame. It becomes the dynasty's arms for all
descendants.

### 5.5 How it is produced

1. **Layers are painted by an image model, not drawn by code.** Every layer in the
   library is generated by an image model from one locked style prompt plus the layer's
   own description, on the shared bust template, so all layers share brushwork,
   lighting and palette. Clothing, headwear and props are painted onto the base bust
   (inpainting) so their edges and shading fit; then cut out as transparent PNGs.
   Painted layers: frog busts per skin, faces per expression, attire per category,
   headwear and regalia per tier, props, backgrounds, banners, frames.
2. A deterministic **compositor** picks layers from tier, genetics and traits using
   `seed = sha256(wallet + artSeed)` and composites them, then applies one shared
   finishing pass (glaze, varnish, brush-texture overlay, craquelure, frame shadow) so
   the layers read as one painting.
3. Optional **harmonisation pass:** a low-strength image-to-image pass with a fixed seed
   over the composite to blend layer edges. Delivered side by side with the plain
   composite so the owner can choose. If used, the output is stored and locked by hash.
4. **Style lock:** before generating the full collection, deliver the style guide, the
   layer library, 12 rendered sample portraits (covering all five tiers and six
   categories) and a contact sheet to the project owner. Full generation starts only
   after the owner approves the style.
5. Regeneration rerolls `artSeed` only: different layer choices within the same tier,
   genetics and traits, never a different style. Every approved image is locked by its
   sha256.

Every Genesis Kekborn has: unique token ID, unique Genesis identity, intended original
owner wallet, rarity, contribution score, genetic attributes, individual visual
characteristics, initial character traits, personality profile, snapshot reference,
permanent Genesis status.

## 6. Metadata and provenance

Structured metadata per Kekborn, created before minting:

- Genesis ID; proposed token ID; intended original wallet.
- Rarity tier; contribution score; contribution categories.
- Genetic attributes; initial character traits; personality profile.
- Snapshot timestamp and block number.
- Original artwork (content hash / IPFS CID), art seed, and the list of layers used.
- Coat of arms.
- Collection: `Kekborn`; token name `Kekborn #<tokenId>`; trait `Generation: Genesis`.

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
5. Style lock: owner approves the style guide, layer library and samples (§5.5).
   Then generate all artwork and initial traits.
6. Create and validate metadata.
7. Present the whole collection in a visual approval dashboard.
8. Owner inspects every Kekborn: artwork, rarity, score, genetics, traits.
9. Per-NFT approval checkbox/action.
10. Approve the whole collection in one action, or individually.
11. Reject individual designs and request regeneration.
12. Regenerate with a new art seed while keeping rarity, verified genetics and trait
    rules unchanged.
13. After approval: contract deployment, minting and distribution, subject to wallet
    authorization.

Dashboard contents: full preview of every Kekborn, recipient wallet, proposed token ID,
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
