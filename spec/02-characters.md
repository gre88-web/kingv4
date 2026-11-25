# 02 — Character System, Genetics and Personality (Phase 1)

One of the most important systems. Every Kekborn has a rich character sheet inspired by
dynastic character simulation. Not just generic stats: distinctive strengths,
weaknesses, virtues, vices, peculiarities and funny behaviour.

Launch target: **at least 300 original traits**, in a data-driven database that can
grow to thousands. Prototype: at least 50. Original terminology, art and text only —
copy nothing from Crusader Kings.

## 1. Trait categories (examples, not limits)

**A. Personality** — Ambitious, Lazy, Greedy, Generous, Paranoid, Reckless, Patient,
Impatient, Arrogant, Humble, Compassionate, Cruel, Honest, Deceitful, Stubborn,
Curious, Cowardly, Brave, Jealous, Charismatic, Antisocial, Obsessive, Dramatic,
Manipulative, Naive, Vindictive, Diplomatic, Chaotic. Influence decisions,
relationships, cooperation, leadership, reproduction, social behaviour.

**B. Virtues** — Courage, Loyalty, Wisdom, Discipline, Generosity, Patience, Creativity,
Justice, Curiosity, Perseverance.
**Vices** — Greed, Envy, Vanity, Gluttony, Sloth, Wrath, Cowardice, Treachery,
Excessive ambition, Self-obsession.
Every trait has situational upsides and downsides: greedy = efficient accumulation but
damaged relationships; courageous = defends the tribe but takes needless risks;
paranoid = detects threats early but cooperates poorly.

**C. Intelligence and mental** — Genius, Highly intelligent, Inventive, Strategic
thinker, Forgetful, Poor judgement, Easily confused, Analytical, Imaginative, Obsessive
researcher, Exceptional memory, Terrible memory, Easily manipulated, Unusually
perceptive. Influence learning, discovery, problem-solving, research, technology.

**D. Social** — Natural leader, Diplomatic, Charismatic, Popular, Unpopular, Persuasive,
Introverted, Tribal loyalist, Opportunist, Gossip, Conflict seeker, Peacemaker,
Excellent negotiator, Terrible negotiator, Born politician, Untrustworthy, Extremely
loyal, Socially awkward. Influence relationships, tribes, alliances, diplomacy,
leadership, institutions.

**E. Congenital and physical** — Unusually strong, Fast runner, Excellent eyesight, Poor
eyesight, Exceptional hearing, Weak constitution, Resistant to disease, Fragile, Large,
Tiny, Unusually agile, Excellent swimmer, Poor coordination, Exceptional stamina,
Distinctive appearance, Rare coloration. Influence survival, movement, combat,
adaptation, reproductive success.

**F. Lifestyle and learned** — Experienced hunter, Master builder, Skilled farmer,
Excellent trader, Natural explorer, Inventor, Military strategist, Scholar, Engineer,
Artist, Diplomat, Merchant, Religious leader, Scientist, Terrible administrator,
Exceptional organizer. **Acquired through actions and achievements, never assigned
randomly.**

**G. Funny and absurd** (central to the game; hundreds needed; each must change
behaviour, not just be cosmetic):

| Trait | Behaviour |
|---|---|
| Certified Idiot | Frequently makes objectively terrible decisions |
| Professional Napper | Sleeps at inappropriate moments |
| Main Character Syndrome | Believes everything revolves around them |
| Delusional Genius | Convinced of genius despite all evidence |
| Uncontrollable Yapping | Cannot stop communicating |
| Suspiciously Wet | Somehow always appears wet |
| Goblin Mode | Prioritizes food, shiny objects, instant gratification |
| Terminally Online | Obsessed with imaginary trends and status |
| Skill Issue | Fails at tasks others find easy |
| Delusions of Grandeur | Believes they are destined to rule the world |
| Chronically Broke | Somehow loses all accumulated resources |
| Absolutely Shameless | No embarrassment or social restraint |
| Professional Hater | Develops rivalries with almost everyone |
| NPC Energy | Rarely makes an independent decision |
| Accidental Prophet | Ridiculous statements that are sometimes correct |
| Suspiciously Lucky | Survives situations that should be fatal |
| Overconfident Strategist | Brilliant plans that rarely work |
| Drama Queen | Turns minor disagreements into major conflicts |
| Legendary Coward | Runs from almost everything |
| Deluxe Couch Potato | Avoids physical activity |
| Secretly Based | Occasionally makes unexpectedly brilliant decisions |
| Walking Red Flag | Others instinctively distrust this Kekborn |
| Tax Evader | Avoids contributing to shared resources |
| Conspiracy Frog | Sees conspiracies everywhere |
| Unemployed Philosopher | Spends all day on the meaning of life |
| Royal Blood, Empty Head | Believes ancestry makes them superior |
| Absolute Menace | Creates problems wherever they go |
| The Chosen One (Self-Appointed) | Convinced of a divine mission |
| Infinite Confidence, Zero Ability | Never questions own competence |
| Accidental Tyrant | Becomes a dictator without meaning to |

## 2. Trait data model

Each trait record: `id`, `name`, `category`, `description`, `icon`, `effects`
(attribute modifiers + behaviour-weight modifiers + event hooks), `opposites`
(incompatible traits), `synergies`, `inheritance` (`genetic` | `partial` | `learned` |
`temporary`), `dominance` (`dominant` | `recessive` | `n/a`), `heritability`
(0–1), `acquisition` (conditions for learned traits), `duration` (permanent or
ticks), `rarity`, `rulesVersion`.

## 3. Character attributes

- Physical: Strength, Constitution, Agility, Speed, Endurance, Perception.
- Mental: Intelligence, Learning, Creativity, Memory, Judgement, Problem-solving.
- Social: Charisma, Diplomacy, Leadership, Persuasion, Loyalty, Deception.
- Behavioural: Aggression, Curiosity, Risk tolerance, Cooperation, Ambition, Discipline.
- Personal: personality traits, virtues and vices, congenital traits, learned traits,
  humorous traits, temporary conditions, relationships, reputation.

Character sheet UI: clear icons, trait descriptions, stats, interactive tooltips.

## 4. Inheritance

Offspring inherit a combination of both parents' genetic and character traits.

- Genetic: physical traits, intelligence predisposition, temperament, disease
  resistance, senses, congenital traits.
- Partially heritable: aggression, curiosity, sociability, risk tolerance, patience,
  ambition, emotional stability.
- Learned (cultural transmission, not genetic): professions, skills, cultural
  practices, knowledge, traditions, languages, political and social behaviour.
- Not inherited: injuries, illnesses, moods, temporary conditions, temporary
  reputation effects.

Rules: never copy all parental traits. Use probabilities, dominance, gene combination
and mutation. Recessive rare traits appear only with the right combination and can
skip generations. Incompatible or contradictory combinations are allowed and should
produce emergent personalities — an intelligent Kekborn with terrible judgement, a
cowardly military genius, a charismatic liar, a lazy genius, a generous Kekborn who is
greedy about food, a legendary warrior terrified of insects.

## 5. Life experience

Traits change during life: repeated victories → confidence or arrogance; defeats →
caution or cowardice; leadership success → charisma; betrayal → paranoia; friendship →
loyalty; exploration → curiosity; discoveries → intellectual traits; wealth → greed or
vanity; long peace → generosity; conflict → aggression. Some changes are temporary,
some permanent. Important events go into the character's history log.

## 6. Dynasties and family trees

Every Kekborn belongs to a traceable lineage: parents, children, siblings, ancestors,
descendants, multiple generations, family traits, dynasty reputation, achievements,
famous ancestors, rivalries, hereditary leadership, inherited titles.

- Players inspect several generations.
- Show which trait came from which ancestor.
- Identify famous ancestors and their influence on descendants.
- Dynasties develop identities (intelligence, war, diplomacy, creativity, stupidity,
  spectacular incompetence) purely from inheritance and simulation, e.g. generations
  of geniuses followed by one spectacularly incompetent heir.
