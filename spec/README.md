# Kekborn — Project Specification

*Born of Kek. Bound by Blood.*

The Evolution of a Living Pepe Civilization.
IMD Genesis Collection, artificial-life simulation and multiplayer evolutionary game.

This folder is the authoritative requirements document for Kekborn. IMD jobs and
goals implement against it. Each job's objective states its own concrete steps; this
spec is the requirements source those steps are checked against.

## Names

| Thing | Name |
|---|---|
| Game and collection | **Kekborn** |
| First NFT drop (IMD holders) | **Kekborn Genesis** |
| Individual Genesis NFT / creature | Genesis Pepe |
| Holders and their lineages | the Kekborn |
| The world | **Kekheim** |
| Tagline | *Born of Kek. Bound by Blood.* |

## Modules

| File | Scope |
|---|---|
| [01-genesis.md](01-genesis.md) | Phase 0: IMD snapshot, contribution score, rarity, genetics, artwork, metadata, owner approval, minting |
| [02-characters.md](02-characters.md) | Phase 1: character traits (300+), attributes, inheritance, life experience, dynasties |
| [03-evolution.md](03-evolution.md) | Phase 2: genome, procedural creatures, the five stages (Cell, Creature, Tribe, Civilization, Space) |
| [04-multiplayer.md](04-multiplayer.md) | Phase 3: persistent shared world, breeding, relationships |
| [05-ai-research.md](05-ai-research.md) | Phase 4: AI analysis and research agents, pattern discovery |
| [06-website.md](06-website.md) | Phase 5: playable browser game and interfaces |
| [07-blockchain-economy.md](07-blockchain-economy.md) | Phase 6: on-chain architecture, future economy |
| [08-architecture.md](08-architecture.md) | Modules, execution order, deliverables |
| [09-security.md](09-security.md) | Security and approval rules (these override everything else) |

## Core vision

Every eligible IMD holder receives one unique Genesis Pepe NFT. Each Genesis Pepe starts
an evolutionary lineage. Through biological evolution, environmental adaptation,
reproduction, social interaction and technology, lineages become different species,
tribes, dynasties and civilizations, and eventually reach space.

Every Pepe has an individual personality and character sheet: traits, strengths,
weaknesses, virtues, vices, quirks and inherited characteristics, inspired by the
dynasty systems of Crusader Kings. Evolution is inspired by Spore. All names, art,
text and trait descriptions are original Kekborn work.

The project combines:

- An IMD-holder Genesis NFT collection.
- Contribution-based NFT rarity.
- Procedural creature generation.
- Dynastic character traits and inheritance.
- Genetic inheritance and evolution.
- Multiplayer ecosystems.
- Social and civilization simulation.
- AI-assisted research and pattern discovery.
- A persistent, player-owned digital universe.

**This is a real computational simulation and a playable game, not AI-generated
storytelling.** Every outcome must come from simulation mechanics.

## Rules that apply to every module

1. Genesis comes first and starts immediately (01-genesis.md), in parallel with game work.
2. Nothing is minted, deployed or distributed before the project owner approves the
   artwork and metadata (01-genesis.md §8, 09-security.md).
3. No fabricated IMD history. Report what is missing instead.
4. Original Genesis attributes are never overwritten by later evolution.
5. The simulation is deterministic and reproducible from a seed and a rules version.
6. If a dependency blocks a task, report the exact blocker and continue with every
   independent task.
