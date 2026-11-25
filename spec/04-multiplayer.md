# 04 — Multiplayer and Persistent World (Phase 3)

## 1. Shared ecosystem

A persistent world where players' lineages coexist: shared ecosystems, persistent
environments, player-owned creatures, cross-player interaction, reproduction and
inheritance, tribe formation, shared settlements, alliances and competition,
civilizations and territory, persistent evolutionary histories.

- Players can inspect other creatures, their owners, ancestry and achievements.
- The world keeps evolving while players are offline (server-side tick loop).
- Scale target: thousands of players, potentially millions of simulated organisms.
  Use region sharding / spatial partitioning and batch ticks.
- Never put creature movement or simulation steps on-chain.

## 2. Breeding and lineages

Parent selection, genetic inheritance, controlled mutation, offspring generation,
ancestry trees, species development, genetic diversity, extinction and survival, rare
combinations, character-trait inheritance, dynasty histories. Descendants get their
own identities; the Genesis NFT identity stays unchanged. Players follow a lineage
across many generations.

## 3. Relationships

Friendships, rivalries, romance, family ties, enmities, alliances, betrayals, loyalty,
jealousy, respect, fear, admiration — stored as per-pair opinion values with typed
modifiers that decay over time.

Traits drive relationships: paranoid Pepes distrust loyal friends; charismatic ones
attract followers; greedy ones betray allies for resources; loyal ones defend family at
great cost; professional haters form rivalries for no reason.

Relationships feed back into cooperation, reproduction, tribe membership, leadership,
diplomacy and conflict.
