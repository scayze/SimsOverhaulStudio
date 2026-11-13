# Relationships, family trees & dynasties — what the game files actually contain

This is the result of a full audit of the installed game, the Tray library and the
save format. It answers one question: **what relationship/family/dynasty data can
be extracted from the files, and what cannot?**

Everything below was verified against the installed game (`D:\Spellen\The Sims 4`),
not from memory of the game.

---

## 1. Household templates (`0xB3C438F0`) — the source for clean premade worlds

These are the resources the studio decodes for **New Overhaul → Game premades**.
There are **207 unique templates** (across all packs) containing **434 sim records**
(the studio's clean-world build de-duplicates repeated builds down to **424 sims /
202 households**).

Each template is a protobuf `FamilyData` → `AccountFamilyData` containing:

* household name, description, funds, lot, inventory markers,
* one `SimData` per sim: name keys, age, gender, species, occult, traits, likes,
  dislikes, skills, careers, aspiration, degrees, milestones,
* `SimData.Attributes` (`PersistableSimInfoAttributes`) with the trackers below.

### What is present and extractable

| Data | Where | Count / notes |
|---|---|---|
| **Mother / Father** | `Attributes.GenealogyTracker.FamilyRelations` (`index` 0/1) | 95 / 70 links |
| **Maternal/paternal grandparents** | same tracker (`index` 2–5) | 5 / 9 / 16 / 1 links |
| **Spouse / partner** | `SimData.SignificantOther` (field 15) | 110 links, **all mutual**, all within the same household |
| **Fiancé(e)** | `SimData.Fiance` (field 68) | 6 links (3 couples), mutual, within the household |
| **Household membership** | `SimData.HouseholdId` + template grouping | 424 sims in 202 households |
| **Children, siblings, grandchildren** | derived by inverting parent links | full graph for the data that exists |
| **Aunts/uncles, cousins, great-grandparents, etc.** | derived transitively from shared parents/grandparents | only where the connecting sim is itself in the world |
| **Dynasty names + descriptions** | `dynastySeed_*` tuning | exactly 8 |
| **Dynasty membership** | household template name segment `EP21_<Dynasty>` / `EP21_<Dynasty>_Townie`, plus the base `Goth` / `Landgraab` templates | inferable membership |

### What is absolutely not in these files

| Missing data | Evidence |
|---|---|
| **Friendship / romance scores** | `Attributes` field 1 (`RelationshipTracker`) is **0 bytes in all 434 sim records** (207/207 templates) |
| **Relationship bits, sentiments, relationship tracks** | The tracker is the only container; it is empty, so there are 0 bits/tracks **in the templates** |
| **Cross-household relationships (in the templates)** | Not one genealogy, `SignificantOther` or `Fiance` target points outside its own template. The cross-household seeds live in the `loot_PremadesSetup_*` tunings — see section 2 |
| **Ex-spouses / ex-partners (in the templates)** | no field for them; the setup tunings can create them (section 2) |
| **Steady partners** | `Steadies` (field 72) is empty in every install template |
| **Deceased / absent relatives** | a handful of genealogy ids point to sims that are not shipped in any template (13 in the de-duplicated world, e.g. the Landry parents, the Behr mother, the Martínez grandmother, the Purdue mother). Their names/records do not exist in the install, so the studio cannot show them |
| **Dynasty id on a sim or household** | no such field in `SimData`, `AccountFamilyData` or `GameplayHouseholdData`; `DynastyTunables` only contains global stats/constants, and `dynastySeed_*` only contains a name + description |
| **Dynasty membership trait** | none. The only dynasty-named trait is `Dynasty Black Sheep` (a story trait on Virgilio Capp), not a membership flag |

### Why the template graph still looks complete

The game stores a **one-directional genealogy record on the descendant** (a child
lists its mother/father/grandparents). The studio inverts those links and adds the
correct inverse (`Child`, `Sibling`, `Grandchild`, `Grandparent`, …). That is why
the tree shows both sides even though each link is stored once.

Only **6 relation types** appear in the install: `Mother`, `Father`,
`Mother's Mother`, `Mother's Father`, `Father's Mother`, `Father's Father`.
Everything else is derived.

---

## 2. Premades-setup tunings (`loot_PremadesSetup_*`) — how a new save gets friendships

This is the missing piece. The household templates only carry family/spouse
seeds. The **extra relationships in a new save** come from the premade setup
`LootActions` tunings: the base/pack `loot_PremadesSetup_*` family and the EP20
`loot_EP20World_NPCs_PremadesSetup_*` variant. The install has **180 such
setups**.

Each tuning is named after the two premade sims it connects, for example:

* `loot_PremadesSetup_EP11_KimGoldbloom_MichaelBell` — Kim Goldbloom (Goldbloom
  household) and Michael Bell (Bell household), i.e. **cross-household**.
* `loot_PremadesSetup_EP17_Ekade_Layne` — Ekade Aether and Layne Coffin.
* `loot_EP20World_NPCs_PremadesSetup_Aeris_Buddy` — Aeris Chavez-Ralston and
  Buddy Scoop (EP20 premade world pair).
* `loot_PremadesSetup_EP13_BayArea_IgnacioRobles_BerniceRobles` — a same-family
  link.
* `loot_PremadesSetup_EP16_HusbandToWife` — role-based setup (husband/wife).

Each setup's `loot_actions` list resolves to data-driven actions such as:

| Action | Meaning |
|---|---|
| `loot_Relationship_Starting_NPC_GoodFriend` | starting friendship level |
| `…_CloseFriends`, `…_Friends` | starting friendship level |
| `…_Lovebirds`, `…_Crush`, `…_SignificantOther` | starting romantic relationship |
| `…_BreakUp` | ex-partners |
| `…_BadMarriage` | married but unhappy |
| `…_Despised`, `…_MildlyDisliked`, `…_Acquaintance` | starting negative/neutral level |
| `loot_Sentiment_AddSentiment_*` | sentiments (Enamored, Adoring, Close, Bitter, Hurt, Furious, …) |
| `loot_FamilyTrope_*`, `loot_RomanceTrope_*` | family/romance dynamics (loving, distant, permissive, cheating, wholesome, steamy, …) |

So the game knows what to do because the **world setup applies these tunings**
after it instantiates the templates: the tuning names identify the pair, and the
loot actions set the relationship track/sentiment/bit. The resulting graph is
then serialized into the save.

### What the studio extracts from them

* **180 setups** found; **110** expose actions (the others are duplicate/empty
  stubs or use a statistics-only form).
* **87 unique pairs** resolve unambiguously to sims in the clean-world dataset;
  **63** of them are cross-household.
* Labels come from the game's action names (Good friend, Close friend, Lovebirds,
  Crush, Ex-partner, Spouse (bad marriage), Despised, Disliked, Acquaintance,
  Family/Romance trope, …).
* The game writes short labels, not exact names, so the studio normalises
  accents (`Chánh` → `Chanh`, `Liên` → `Lien`) and applies a small alias table
  for typos and the genuinely ambiguous first names (`Toshi`→Toshie,
  `Daliha`→Dahlia, `DomiqueSoto`→Dominique Soto, `Olive`→Olive Specter,
  `Sara`→Sara Chavez-Ralston, `Lily`→Lily Zhu, `Ollie`→Ollie Mark).
* Role-based names (`HusbandToWife`, `FamilyParent`, `HorseTrainer`,
  `AnimalFamilySimChild`, `ElderWomanToChef`, EP10 archetypes) are applied by the
  game to whichever sims hold the role at runtime; they do not identify a sim in
  the tuning, so they are skipped rather than guessed. The household templates
  already carry those families' actual links.

The exact numeric track values live inside the individual loot-action tunings;
the studio uses sensible defaults for the two sliders (the label and the game's
sentiment bits are the authoritative part) and both are editable.

### Skill levels, milestones and identity traits

* **Skill levels are computed from the binary XP value** using the game's
  XP-to-level curve (1,000 → 2, 3,000 → 3, 5,000 → 4, 12,000 → 5, 19,000 → 6,
  29,000 → 7, 43,000 → 8, 60,000 → 9, 80,000 → 10). This matches the game/wiki
  values: Tybalt Capp Painting 8 / Piano 6 / Swordsmanship 7 / Charisma 9,
  Bella Goth 2/2, Mortimer Goth Writing 4, Salim Benali Writing 8 / Cooking 3 /
  Video Gaming 4. The `_skills` ranges are **not** levels and are no longer used
  for this.
* **Starting milestones come from install files.** `PremadeSimTemplate._fixups`
  can reference a `SimInfoFixup` with a
  `developmental_milestone_ops_fixup_action`; that action lists the milestone
  ids the sim starts with. The studio extracts these ids and resolves them
  through the milestone catalog (42 premade sims in this library; e.g. Aeris
  Chavez-Ralston starts with Childhood Phase, Agora Tchotchke with Got Fired and
  High School Expelled). This is **not** Tray data.
* **Tray milestones are only used for explicitly imported Tray/save sims.** The
  Tray tracker is `field 47 -> 27`; Bob Pancakes, for example, has 90 stored
  milestones in his Tray export. They are never copied onto premade sims.
* **`trait_GenderMale` / `trait_GenderFemale` are filtered out.** Gender is an
  identity value (`field 7` / the Identity card), not a personality trait.

### Household-specific bits (`PremadeHouseholdTemplate`)

There is a second tuning that the binary templates do **not** expose:
`PremadeHouseholdTemplate` (class `PremadeHouseholdTemplate`). Its
`_household_relationship` list stores the specific relationship between
household members:

* `living_roommate` — e.g. **Free Spirits** (Maaike Haas + Ulrike Faust) and Bro
  (Joaquin Le Chien + Sergio Romeo).
* `RomanticCombo_Lovebirds` — e.g. Fyres (Dominic + Moira) and Bjergsen
  (Bjorn + Clara).
* `RomanticCombo_Lovers`, `RomanticCombo_ItsComplicated`,
  `RomanticCombo_HotAndCold`, `RomanticCombo_Soulmates`,
  `RomanticCombo_Sweethearts` — Partihaus, Riviera, HS Price, …
* `friendship-bff`, `friendship-good_friends`, `friendship-friend`,
  `friendship-acquaintances`, `friendship-disliked` — e.g. Harris, Maker,
  Ngata, Fyres children.
* `family_Target_IsBrotherSisterOf_Actor`,
  `family_Target_IsAuntUncleOf_Actor` — Kealoha, Odd Twins.
* `romantic_FirstKiss`, `romantic-HaveDoneWooHoo`,
  `relbit_SocialContext_Romance_Amorous/Steamy` — Entrepreneur, Jang, Hu.

The studio extracted **78 households** with these bits and adds them to the
matching relationship rows (e.g. Free Spirits now shows **Roommate**, not just
"Household member"). Member names that are internal template names
(`ThorKnutson` for Paolo Rocca) or that only exist in one direction are skipped
rather than guessed.

The same `_household_relationship` list also carries **family enum entries**
(`FATHER`, `MOTHER`, …) and **family bits** such as
`family_Target_IsBrotherSisterOf_Actor` and
`family_Target_IsAuntUncleOf_Actor`. The binary genealogy only stores
parents/grandparents, so these tuning entries are the extra source for
siblings/aunts/uncles and for households whose parent links are not in the
binary template. The extraction now covers **78 households / 138 family enum
entries** plus the family bits. Member names are resolved through the English
STBL (`simTemplate_ThorKnutson` → **Paolo Rocca**), so internal template names no
longer cause skipped links. The studio adds them to both the **Family links**
list and the **Family tree**. Examples: Kealoha (Duane is Nani's aunt/uncle and
Lilliana's sibling), Charm, Odd Twins and the Wilsons (siblings), Delgato,
Bailey-Moon, Ngata, Lynx and many more parent links.

### Club memberships (`PremadeSimTemplate.clubs`)

Clubs are a separate social system, but the game's relationship panel has a
**club filter** that lists the members. Each premade sim's clubs are stored in
`PremadeSimTemplate.clubs` (a club-seed id), and the club seed's `name` gives
the club name. The install defines 11 premade clubs, including:

| Club | Members |
|---|---|
| **Avant Gardes** | Maaike Haas, Yuki Behr, Gunther Munch, Hugo Villareal |
| **Renegades** | Ulrike Faust, Max Villareal, Wolfgang Munch, Morgan Fyres |
| Partihaus | Eva Capricciosa, Jade Rosa, Thor Knutson, Marcus Flex |
| Paragons | Sergio Romeo, Luna Villareal, Sofia Bjergsen, Siobhan Fyres |
| Powerhouse | Clara Bjergsen, Thor Knutson, Marcus Flex |
| Upper Crusts | Clara Bjergsen, Mila Munch, Hugo Villareal |
| Knights of the Hedge | Jacques Villareal, Yuki Behr, Wolfgang Munch |
| The Good Timers | Jacques Villareal, Mila Munch, Bjorn Bjergsen, Dominic Fyres |
| League of Adventurers | Lucas Munch, Max Villareal, Elsa Bjergsen |
| Garden Gnomes | Lucas Munch, Bjorn Bjergsen, Moira Fyres |
| Spin Masters | Candy Behr, Joaquin Le Chien, Dominic Fyres |

The studio adds a **"Club member: <club>"** link between members who have no
other relationship, and a club bit to existing links. This is why the Free
Spirits now show Maaike connected to Yuki/Gunther/Hugo and Ulrike to
Max/Wolfgang/Morgan.

**Are the club links friendships?** No — and the files are unambiguous about it.
Every `clubSeed_*` tuning contains only `club_description`, `club_rules`,
`hangout`, `icon`, `initial_number_of_memebers`, `membership_criteria`, `name`,
`unlocked_rewards` (and optionally outfit/uniform/colour fields). There is **no
relationship track, friendship value or relationship-bit list** in any club
seed, and the save-side `Club` message stores only `Leader` + `Members` (plus
rules/hangout/uniforms). So the game does **not** seed friendship scores between
club members at new-save creation. The relationship panel’s club filter lists
membership; actual friendships are generated by club gatherings and social
interactions during play and live in the save. The studio therefore represents
club membership as a separate “Club member” link (0/0 sliders), not as a
pre-existing friendship.

### Dynasties: exact members, roles and ancestors

The install has three dynasty-related tuning families:

| Tuning | What it stores |
|---|---|
| `PremadeSimTemplate.dynasty` | **exact membership**: dynasty seed + `is_head` / `is_heir` / `is_black_sheep` |
| `DynastySeed` | name, description, ideals, skills, allies, rivals, unlocked perks |
| `TunablePremadeAncestor` | the **deceased ancestors** shown in the family-tree tapestry: full name, gender, death type, noble title, region, thumbnail |

The studio extracts all of them (8 dynasties, 17 living members with roles, 20
ancestors). Examples:

**Capp** — head **Tybalt**; heir **Beatrice**; **Celeste**; black sheep
**Virgilio**; **Consort**. Ancestors: **Caliban Capp**, **Cordelia Capp**
(Grand Duchess of Ondarion, died by fire), **Contessa Capp** (died of old age).
Ideals: Connoisseur, Artistic, Diplomatic. Skill: Piano. Rival: Monty.

**Thebe** — head **Cordelia Thebe V**; heir **Thiago Abrantes**. Ancestors:
**Eetion Thebe** (Duke of Ondarion), **Cordelia Thebe II/III/IV** (Grand
Duchess/Marchioness), **Hector Thebe**, **Andromache Thebe**. Ideals: Bold,
Nature, Jolly. Skills: Logic, Bartending, Swordsmanship.

The two base-game dynasties (**Goth**, **Landgraab**) have no
`PremadeSimTemplate.dynasty` field, so they fall back to the household-template
tag (which is exact for those two).

The living-tree edges are the genealogy/family bits plus the EP21 NPC seeds
(below). The ancestors are the game's **family-tree tapestry** lineage. They are
attached to every sim whose family name matches (Capp, Thebe, Ananou, Kealoha,
Grove, Gomes, Kunal, Vatore, Zhu, …) and are inherited along parent edges, so
**Juliette Monty (née Capp)** and her son **Dante** keep the Capp ancestors even
though their surname is Monty. The ancestor list itself is a lineage: the files
do not encode explicit parent edges for the deceased figures, so the studio
shows them as a lineage rather than inventing spouse/parent links.

### The Capp/Monty tree as the game defines it

Combining the household template, the EP21 NPC seeds and the dynasty ancestors
gives the complete Capp/Monty graph:

```
Caliban Capp ── Cordelia Capp (Grand Duchess of Ondarion)
                    │
             Consort Capp ── Contessa Capp
                    │
        ┌───────────┴───────────┐
     Tybalt Capp            Juliette Monty (née Capp)
        │                        │  ⚭ Romeo Monty
  Beatrice (heir)               Dante Monty
  Celeste
  Virgilio (black sheep)
```

* Tybalt is **Head**; Beatrice is **Heir**; Virgilio is **Black Sheep**.
* Tybalt ↔ Juliette: siblings, friendship **−90**, Bitter grudge (the game's
  own tuning; Tybalt’s bio calls Juliette “his sister”).
* Consort → Tybalt and Juliette: father/child, difficult-family trope + Bitter.
* Tybalt ↔ Virgilio: friendship **−70**, Furious + Dynasty Resentful Black Sheep.
* Tybalt ↔ Romeo: friendship **−80**.
* Celeste ↔ Beatrice: Close sentiment (both directions).
* Juliette ⚭ Romeo → Dante (Spouse/Child from the Monty household template).

### Premade secrets (`SimInfoFixup` → `secrets_fixup_action`)

EP21 seeds five premade scandal secrets, which are additional hidden
connections (not friendship scores):

| Sim | Secret | Other party |
|---|---|---|
| Celeste Capp | `secret_ScandalSecret_Dynasty_ForbiddenFriends` | Dante Monty |
| Cordelia Thebe V | `secret_ScandalSecret_SecretLovers` | Mara Acosta |
| Adekoya Darong | `secret_ScandalSecret_hasSecretChild` | Aghata Ananou (ancestor) |
| Mara Acosta | `secret_ScandalSecret_EP21World_MaraAcosta` | — |
| Connie Fidential | `secret_ScandalSecret_isInfoBroker` | — |

These are secrets, not friendship scores: the studio does not turn them into
slider values. The owner is resolved from the sim template's `_fixups` list, not
from the fixup name. Paired secrets become a “Secret: …” bit on both sims and
appear in the **Secrets** card in the Links view; single-sim secrets and
ancestor targets are listed there by name. Where a secret coincides with a
seeded connection it is already visible through that link (Cordelia/Mara =
romance 80 + Enamored/Secret Love; Adekoya/Aghata = the Ananou ancestor line),
and the audit keeps the secret name so the hidden context is not lost.

**Sentiments and bits:** the install's premade sentiments/bits are the ones in
the household tunings (roommate, lovers, lovebirds, disliked, sibling/aunt, …),
the `loot_PremadesSetup_*` / EP20 setups (Enamored, Adoring, Bitter, Hurt, …),
and the EP21 `loot_WorldEP21_NPC_*` seeds (exact friendship/romance values,
`Bitter grudge`, `Furious`, `Close`, `Enamored/SecretLove`, family/romance
tropes). The EP21 **family-tree secrets** (`loot_FamilyTree_SecretChild`,
`SecretLover`, `Forgery`, `tapestry` interactions) remain runtime mechanics; the
premade secret seeds above are the five the game ships in the world.

---

## 3. Tray exports (`.householdbinary`) — optional imports

Tray files are richer than install templates, because they are exports of played
households:

| Data | Present? | Notes |
|---|---|---|
| Genealogy | ✅ | **1,775 entries** across 1,380 sim records in 590 households |
| Spouse / partner (`SignificantOther`) | ✅ | same field as templates |
| Fiancé(e) (`Fiance`) | ✅ | 19 records set in the audited Tray library |
| Steady partner (`Steadies`) | ✅ | 10 records set |
| Relationship scores / bits / tracks | ⚠️ rare | Only **6 of 590** households contain a non-empty relationship tracker (31 relationship entries with bits/tracks). Most Tray households store only genealogy + partner |
| Cross-household links | ⚠️ possible | Tray trackers can target sim ids outside the exported household (e.g. a fiancé or a household member who was not in the export). The file contains the id, but **not the target's name** |

The studio now reads genealogy, spouse/partner, fiancé(e) and steady links from
Tray files. It cannot name a Tray target that is not part of the same exported
household; those links are dropped until that sim exists in the project.

---

## 4. Save files (`.save`)

A save contains the **full runtime graph** (friendships, romance, all relationship
bits, cross-household links, dynasty/legacy state, etc.) — the game must have it.
However, it is stored in the game's **proprietary persistence serialization**
(mixed RefPack/zlib chunks inside resources such as type `0x0D`), not as the
self-describing protobuf used by household templates.

What the current reader can extract from a save:

* ✅ sim names, household grouping, save/household artwork
* ✅ traits/skills/careers/etc. when the same sim can be matched to a Tray export
* ❌ the save's own relationship graph

Extracting the save relationship graph would require a dedicated deserializer for
the persistence format. It is technically possible, but it is a separate project
from the template/Tray readers.

---

## 5. Dynasties - the definitive answer

**What exists:**

* 8 `dynastySeed_*` tunings: **Abrantes, Alto, Capp, Darong, Goth, Landgraab,
  Monty, Thebe**. Each ships the name/description (STBL), ideals, skills,
  allies/rivals and unlocked perks.
* **`PremadeSimTemplate.dynasty`** on the EP21 premade sims: the exact dynasty
  `seed` plus `is_head`, `is_heir` and `is_black_sheep`. This is the authoritative
  membership/role source.
* **`TunablePremadeAncestor`** tunings: the deceased family-tree tapestry
  figures (name, gender, death type, noble title/region, thumbnail).
* EP21 household templates whose names contain the dynasty segment
  (`premadeHouseholdTemplate_EP21_Monty`, `…_EP21_Capp_Townie`, …).
* The base `premadeHouseholdTemplate_Goth` and `…_Landgraab` — the only two
  dynasty seeds without an EP21 prefix.
* Hidden character traits such as `trait_Hidden_Ep21World_IsCapp` /
  `IsMonty` / `trait_Hidden_isDarong`. These are per-character markers, not a
  complete membership list (Consort Capp has no `IsCapp`; Dante has no
  `IsMonty`), so they are used for validation only.

**What does *not* exist:**

* no `dynasty_id` field on a household,
* no list of sim ids or household ids inside the dynasty tunings,
* no cross-household dynasty relationship data.

**Therefore the membership rule is:**

> A sim belongs to a dynasty when their `PremadeSimTemplate.dynasty` seed points
> at that dynasty. For the two base dynasties that have no such field (Goth,
> Landgraab), fall back to the exact base household template.

The studio uses exactly that rule. It does **not** match surnames or display names
(which is why Holly Alto’s unrelated base “Alto” household is not in the EP21 Alto
dynasty, and why Joana Abrantes is not automatically an Abrantes-dynasty member).
A sim who marries into a dynasty but lives elsewhere, or a dynasty member who
moves out, cannot be placed from the install — only a save knows that.

---

## 6. One-paragraph summary

From the **installed game** you can extract the complete **family graph that the
templates define** — parents, grandparents, spouses/partners, fiancé(e)s,
household membership, and everything derivable from those (children, siblings,
grandchildren, aunts/uncles, cousins) — plus the eight dynasty names/descriptions.
The templates do **not** store friendship/romance scores, bits or cross-household
links, but two tuning families do: the **`PremadeHouseholdTemplate`** tunings
carry the specific household bits (roommate, lovers, lovebirds, BFF, disliked, …)
for 78 households, and the **`loot_PremadesSetup_*`** tunings carry 180 setups
that resolve to starting friendships, close friends, lovebirds, crushes, exes,
bad marriages and rivalries between premade sims, including cross-household
pairs (plus the EP20 `loot_EP20World_NPCs_PremadesSetup_*` pairs). **Club
memberships** (`PremadeSimTemplate.clubs`) add the relationship panel's club
links (11 clubs, e.g. Avant Gardes / Renegades). The studio applies **87 unique
resolved setup pairs** (63 cross-household), the household-specific bits, the
club links, the **20 family-tree ancestors**, the **5 premade scandal secrets**
and the exact dynasty roles. **Tray exports** add fiancé(e)/steady partners and,
rarely, relationship scores/bits. **Saves** contain the complete runtime graph,
but in a proprietary serialized format that would need a dedicated reader.
