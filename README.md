# Sim Overhaul Studio

A local, Body Shop–inspired studio for The Sims 4. Browse the sims in your saves
or Tray library, edit their relationships, skills, traits, careers, funds,
occults, degrees and milestones, then export the whole thing as a new-save
overhaul mod.

Built with Python, Pillow and a Clean UI style web frontend.
Game/save/Tray extraction is powered by the bundled, unmodified
[SimsDataSDK](SimsDataSDK/) checkout; see
[`docs/sdk-migration.md`](docs/sdk-migration.md) for the coverage map and the
precise list of features still implemented locally.

---

## Start the studio

Double-click **`Start Studio.bat`**.

Install the bundled SDK's Python dependency with `python -m pip install Pillow`
if Pillow is not already available. The SDK uses it to convert game images to PNG.

The studio opens in an Edge/Chrome app window at `http://127.0.0.1:8765`.
Keep the console window open while you work; closing it stops the studio.
Nothing is installed system-wide.

If you prefer a normal browser, open `http://127.0.0.1:8765` yourself.

---

## What it reads (always read-only)

| Source | What the studio uses |
| --- | --- |
| `Documents/Electronic Arts/The Sims 4/saves` | Households + sim names, save artwork, household thumbnails |
| `.../The Sims 4/Tray` | Household + sim names from `.householdbinary` files |
| Game install (`D:\Spellen\The Sims 4`) | Traits, skills, careers, aspirations, milestones, preferences from all installed packs; premade household templates and their group portraits (client/thumbnail packages) |
| `.../The Sims 4/Mods` | Custom traits/careers/etc. from XML tuning, marked **MOD** |

The studio **never writes into** your saves, Tray or game folder. It only reads.
Your project is stored in `projects/active_project.json` and exports go to
`exports/`.

---

## Workflow

1. **New Overhaul** (top bar) → name your new-save template project.
2. **From Saves** or **From Tray** → pick a household or sim → *Add*.
3. Edit in the tabs: Identity, Traits & Aspiration, Skills, Career & Degrees,
   Relationships, Milestones & Likes.
4. **Export Mod** → a folder appears in `exports/` with:
   - `YourName.ts4script` — the overhaul mod
   - `YourName_config.json` — the project data, for reference
   - `README.txt` — install instructions
5. Copy the `.ts4script` into `Documents/Electronic Arts/The Sims 4/Mods`.
6. Start a new save, or load an existing one and run `simoverhaul.apply` in the
   cheat console (`Ctrl+Shift+C`).

The exported mod matches sims by **first + last name and household** and applies
the changes once when a zone finishes loading. Sims that do not exist are skipped
safely. A report is written to
`Documents/Electronic Arts/The Sims 4/SimOverhaul_report.txt`.

---

## What gets imported

**From the game's clean premade templates (New Overhaul → Game premades):**
- Household name, description, starting funds and lot (where the game provides it)
- Sims exactly as they start in a new save: name, age, gender, species, occult
- A **full decode of every household template** in the installed game
  (`backend/templatedata.py`, powered by SimsDataSDK): **200 households / 425
  standard sims**, including the newer EP19–EP21 families and NPC/townie
  templates the old bundled data missed. Names resolve through the SDK's merged
  English STBL tables. It reads all traits, **likes and dislikes** (1,821 / 673),
  skills with levels, careers with
  their level and **specialisation**, aspiration, degrees and milestones.
- **Skill levels come from the binary XP curve.** The binary template stores XP;
  the studio converts it with the game's XP-to-level curve (1,000 → 2, 3,000 → 3,
  5,000 → 4, 9,000 → 5, 15,000 → 6, 25,000 → 7, 40,000 → 8, 60,000 → 9,
  80,000 → 10). Child and toddler fundamentals use their own curves (child
  1,100 → 2, 2,780 → 3, 7,749 → 5, 14,309 → 7; toddler 299 → 2, 579 → 3), and
  Vampire Lore uses its 15-level curve. Tybalt is Painting 8 / Piano 6 /
  Swordsmanship 7 / Charisma 9; Bella is 2/2; Mortimer Writing 4. The `_skills`
  ranges are not levels and are no longer used for this.
- **EP21 careers come from the install template too.** `PremadeSimTemplate.career_level`
  points at a career-level tuning such as `career_Writer_Journalist_Level1` or
  `career_Noble_Level9`; the studio resolves that to the career, track and
  starting level. Aspirations are stored as an **aspiration track** (e.g.
  `Popularity B`), not always a specific aspiration, so the tool shows the track
  where the file only defines the track.
- **Pronouns and gender identity come from `SimInfo`.** The template's gender
  field is the physical frame. Custom `SimInfo` resources store the pronoun set
  (`she/her`, `he/him`, `they/them`, neopronouns); non-binary identities are
  shown as **Non-binary** with the physical frame kept separately.
- **Inferred links are marked.** Family links that come from tuning family
  tropes rather than explicit genealogy are labelled **Inferred** in the tree
  and Links view. The install files do not encode every ancestor edge.
- **The CAS gender trait is omitted.** `trait_GenderMale` / `trait_GenderFemale`
  is an identity flag, not a personality trait; gender already comes from
  `Identity`.
- **A visual family tree.** Family links open a card-based tree with portraits,
  direct parent/child units, solid parent/child lines and dashed partner lines.
  Generation labels are not shown. Under **Family links** you can add Parent,
  Child, Sibling, Spouse, Fiancé(e), Steady, Grandparent, Grandchild,
  Aunt/Uncle, Niece/Nephew or Cousin; the inverse link and relationship row are
  created automatically.
- Aspiration tracks (for example `Knowledge A`) are shown as tracks. The install
  files do not store the specific aspiration, so the studio does not invent one;
  you can choose a specific aspiration yourself.
- A **complete relationship graph**: every family link on both sides, spouses,
  siblings, grandparents, aunts/uncles, cousins and a friendship entry for every
  household member — plus the SDK's **PremadeSimRelationships** extraction
  (348 cross-household pairs), including friendships, romances, exes and
  rivalries — as a fresh save shows. The EP21 `loot_WorldEP21_NPC_*` seeds add the
  Bellacorde social/family graph with exact scores and sentiments (Tybalt ↔
  Juliette −90 + Bitter, Consort → Tybalt/Juliette, Tybalt ↔ Virgilio −70,
  Juliette ⚭ Romeo → Dante, …).
- The game's own **family-tree ancestors** (`TunablePremadeAncestor`) for every
  matching family name — Capp, Thebe, Ananou, Kealoha, Grove, Gomes, Kunal,
  Vatore, Zhu and more — including noble titles, regions and death types. They
  follow the parent line, so Juliette Monty (née Capp) and Dante keep the Capp
  ancestors even after the surname changed.
- The game's **premade scandal secrets** (`SimInfoFixup` →
  `secrets_fixup_action`): Celeste Capp ↔ Dante Monty, Cordelia Thebe V ↔ Mara
  Acosta, Adekoya Darong → Aghata Ananou, plus the single-sim secrets. Paired
  secrets appear as “Secret: …” bits on both sims and in a **Secrets** card in
  the Links view; they never overwrite friendship/romance scores.
- The game's own **household picture** for each clean-save household. No Tray
  picture matching and no guessed per-sim crops are used — those would show a
  different sim, so premade sims show the game's exact household image instead.
  A sim imported from the Tray keeps its own `.sgi` portrait.
- Exactly the **eight dynasties the game defines** (`dynastySeed_*` tuning).
  Membership is the exact `PremadeSimTemplate.dynasty` field (seed + head /
  heir / black-sheep role), with the household-template tag as the fallback for
  the base Goth/Landgraab households. Each card also shows the dynasty's
  ideals/skills/rivals and its premade ancestors with titles and death types.
  The list is editable and you can add your own.
- No Tray files are read for the gameplay data of this source.

**From Tray (`householdbinary`):**
- Name, age, gender, species, occult
- Personality traits and reward traits
- Likes and dislikes, grouped by category in a single picker
- Skills with current estimated level
- Current career + levels, plus career history
- University degrees
- Spouse / partner links and **parent / child / sibling family links**
- **Starting milestones come from install files.** `PremadeSimTemplate._fixups`
  → `SimInfoFixup.developmental_milestone_ops_fixup_action` lists the milestone
  ids a premade sim starts with. 40 premade sims in this library have seeded
  milestones (e.g. Aeris gets Childhood Phase; Agora gets Got Fired and High
  School Expelled). This is **not** Tray data.
- **Tray milestones are only used for explicitly imported Tray/save sims**
  (field 47/27). They are never copied onto premade sims.
- Family relationship entries (default 60 friendship / 0 romance) so they can be adjusted
- Aspirations read from Tray item text when present
- Earned milestones when the Tray tracker exposes them
- Sim portrait (`.sgi`) and household artwork (`.hhi`)

**From saves:**
- Name, household and save artwork
- When the same premade exists in your Tray library, the studio automatically
  matches it and fills in traits, skills, careers, likes/dislikes, degrees,
  spouse and family links (`Tray match` badge), plus the sim portrait.
- Sims without a Tray match show `Name only`.
- **New Overhaul** can also copy every household from a specific save, or start empty.

You can add Tray sims after creating a project, and **Replace data from Tray…**
copies a Tray sim's traits/skills/career/aspiration/likes/portrait onto a selected
premade sim while keeping its name and household so the mod still targets it.

---

## Catalogs

- **Batuu (GP09) content is hidden by default**; use the *Include Batuu* toggle.
- **NPC / service jobs are hidden by default**; use *Include NPC jobs*.
- **Compatibility filters really work.** Age, species and occult restrictions are
  derived from the Sims 4 icon-pack folders and tuning names, so *Only compatible
  with [age]* shows only traits/skills/careers that can actually be assigned to
  the selected sim (e.g. toddler traits only for toddlers, teen jobs only for
  teens). Species/occult filtering uses the same data.
- Hidden/internal traits (gender options, reputation, walk styles, age markers,
  competition markers, scenario/quest markers, university tricks, etc.) are
  removed from the catalog.
- **Sims 4 game icons** are used for traits, skills, careers, aspirations,
  milestones and degrees. The tabs themselves keep the Sims 2 icons.
- Aspirations are shown **once per aspiration**; the game's A2/A3/A4 tiers are
  hidden and applied automatically.
- Degrees are stored by the game as traits, so the exporter applies them as
  traits. Degrees are grouped by **major** in the catalog, with internal
  "Degree Traits …" markers hidden.
- **Trait conditions are short and specific** — one line naming where the trait
  comes from (CAS personality, Reward Store, aspiration/career reward, bonus,
  lifestyle, fear, toddler/infant/child-teen, pet, occult perk, sentiment, modded,
  …). The *Condition guide* in the Trait Catalog lists them all. No generic
  explanations are repeated on skills, careers, degrees, milestones or
  aspirations.
- **Everything is one unified catalog.** Careers are grouped by type (full-time,
  active, university & education, part-time, teen/child, after-school, freelance,
  NPC/service, quests, modded); degrees by major; career specialisations by
  career family. In game a career runs from level 1–10 and each branching career
  splits at its own level, read from the game's `careerLevels_*` tunings
  (Business 7, Astronaut 8, Athletic 5, Civil Designer 4, Criminal 6,
  Social Media 4, …) — the Career tab lets you set the career, its level and its
  specialisation together, and specialisations stay locked until that level is
  reached. The shared pre-branch track is never offered as a specialisation.
  Discover University enrolment is the real **University student (active)**
  career, with its four course slots as specialisations.
- **Reward traits carry their effects.** Career / aspiration reward traits in the
  trait catalog note the matching (ex-)career, aspiration and skills; adding one
  also applies those to the sim automatically.

---

## Wiki audit

The studio includes a repeatable audit that compares every matched wiki page
with the install-derived project:

```powershell
python tools/wiki_audit.py          # fetch/compare 390 wiki pages
python tools/make_audit_report.py   # write data/audit_report.md
```

Outputs:

- `data/wiki_audit.json` — per-sim diffs, wiki skills and tool skills
- `data/wiki_skill_pairs.json` — every wiki/tool skill pair, for curve checks
- `data/audit_report.md` — readable summary + the actionable per-sim list

The audit separates **track-only aspirations** (the install stores a track, not
a specific aspiration), **level-1 baseline skills** (the template's 100 XP
floor) and **extended family links** (the infobox usually lists only immediate
family) from real install-vs-wiki differences.

---

## Notes & current limits

- **Tray files are blueprints.** The studio cannot create brand-new sims inside
  a save. Place the household from the Gallery in your save, then the exported
  mod applies the overhaul by name + household.
- **The exported mod is defensive.** Every action is wrapped; a missing pack or
  changed game API is logged instead of breaking the save.
- **Modded tuning is detected from XML tuning** in your Mods folder. Packages
  that ship only binary tuning will show up as EA content, not as MOD.
- **Clean premade sims come from the game's household templates.** They are
  read-only and use the game's own starting data, not your Tray or saves.
- **Some data is genuinely absent from the install.** The audit's remaining
  flags are mostly: specific aspirations (only tracks are stored), ancestor
  parent edges (not encoded for every dynasty), reward/aspiration traits that
  the wiki lists but the template does not contain, a few skill seed values that
  differ from the wiki's played-save state, and mods/NPC jobs that have no
  normal career entry. These are flagged, not fabricated.
- **No Tray picture matching.** The studio never borrows a Tray sim's portrait for
  a premade — those are different sims. Clean-save sims show the game's own
  household picture (cached in `data/premade_images/`). Only a sim you explicitly
  import from the Tray uses that Tray sim's `.sgi` portrait.
- **Portraits use the game's alpha masks.** Both household images and `.sgi`
  portrait thumbnails are masked with the embedded `ALFA`/`ALFJ` data, using a
  crisp alpha ramp for sim portraits, so the game's soft white glow is cut into a
  clean edge instead of a blurry halo. Households whose artwork ships without a
  mask simply render unmasked (no broken-image/404).
- **Relationship defaults:** spouses use 45 friendship / 75 romance, family
  members 45 / 0, and other household members 15 / 0. Household templates do not
  store numeric relationship scores, so these are the game's starting defaults.
  Every family link is bidirectional with the correctly inverted relation, so
  spouses/children/parents are never confused.
- **Relationships** has three views: *Links* (friendship/romance sliders and
  direct family links), *Family tree* (a direct parent/child tree with couple
  units and visual parent/child lines; no generation labels) and *Dynasties*.
- **Dynasties are the game's own.** Exactly the eight `dynastySeed_*` tunings
  shipped by the game (Abrantes, Alto, Capp, Darong, Goth, Landgraab, Monty,
  Thebe) are listed. Membership is the exact `PremadeSimTemplate.dynasty` field
  (seed + head/heir/black-sheep role), with the household-template tag as the
  fallback for the base Goth/Landgraab households. Each card also shows the
  dynasty's ideals/skills/rivals and its **premade ancestors** from
  `TunablePremadeAncestor` (e.g. Caliban, Cordelia and Contessa Capp; Eetion,
  Cordelia II–IV, Hector and Andromache Thebe) with their noble titles and death
  types. You can still edit existing dynasties or add your own.
- **Genealogy labels are normalised.** The template's `Father's Mother` becomes
  "Grandmother (paternal)"; siblings, grandparents, aunts/uncles and cousins are
  derived from the shared-parent graph.
- **Aspiration tracks** such as “Popularity C” are shown as tracks. The install
  template does not store the specific aspiration inside the track, so the studio
  leaves it unset until you choose one. The audit reports these separately from
  real aspiration mismatches.
- **Careers & specialisations.** Levels run 1–10. Only careers the game actually
  branches offer specialisations, and each career unlocks at its own branch level
  read from the game's `careerLevels_*` tunings (Business 7, Criminal 6,
  Astronaut 8, Athletic 5, Civil Designer 4, Critic 4, Education 6, Military 6,
  Park Worker 8, Social Media 4, …), staying locked before it. Careers with no
  branches say so. Discover University enrolment is exposed as the real
  **University student (active)** career with its four course slots.
- **Reward traits have effects.** Granting a career/aspiration reward trait also
  applies the matching (ex-)career to career history, the matching aspiration and
  relevant skills where the game data provides them.
- **Milestones & relationship bits are explained.** Each milestone entry says when
  it would normally be earned in game (and the redundant "Life Milestone" prefix is
  dropped), and each relationship bit / sentiment says what kind of connection it
  represents.
- **Relationships come from the genealogy and the game's tunings.** The household
  templates contain the family graph, spouses and fiancé(e)s; the
  `PremadeHouseholdTemplate` tunings add the specific household bits (Roommate,
  Lovers, Lovebirds, BFF, Disliked, …) and 138 extra family links (parent,
  sibling, aunt/uncle) across 78 households; the `PremadeSimTemplate.clubs`
  tunings add the relationship panel's club links (Avant Gardes, Renegades, …);
  and the SDK's `PremadeSimRelationships` extraction adds the extra friendships,
  romances, exes and rivalries a new save starts with, including cross-household
  pairs. See `docs/relationships-dynasties-audit.md` for the complete audit.
- **Badge icons are normalised and sized.** The life-stage, male/female and occult
  glyphs are cropped to their visible area, rendered in a fixed box, centred, and
  the gender glyphs are sized to match the occult icon. Occult badges use the
  Sims 4 `Misc Traits/Life States` icons (Vampire, Werewolf, Spellcaster, Mermaid,
  Alien, Ghost, PlantSim, Servo, Fairy) instead of the older Sims 2 glyphs.
- **Per-sim options** (the **⋯** menu next to the ✕ in the Sims list) has exactly
  three actions: *Replace data from Tray…* (pick a Tray sim, then tick exactly
  which fields to replace — list fields merge so your edits survive, and a
  before/after diff is shown with an Undo), *Reset to game template* (restores
  values from the
  project's origin — clean new-save world, a save file, or Tray), and *Remove sim*.
- **Likes & dislikes.** Both the Milestones & Likes tab and the picker show your
  current likes/dislikes first with a one-click ✕ to remove each, then the add
  list — no separate hunt through a long list to undo one.
- **Badge icons are normalised.** The life-stage, male/female and occult glyphs are
  cropped to their visible area and rendered in a fixed box so they line up and are
  the same size.
- **Starting funds are read from the clean premade template** (for example the
  Goths start at §45,500 and the Landgraabs at §85,000). Tray blueprints do not
  contain funds.
- **Existing saves:** the studio never writes into a `.save` file. Instead the
  exported `.ts4script` can be applied to an existing save — load it and run
  `simoverhaul.apply` in the cheat console. The game itself then writes the
  changes into that save.
- Test the exported mod on a **new save** first.

---

## Troubleshooting

- **"No saves found"** — check that `Documents/Electronic Arts/The Sims 4/saves`
  exists and contains `.save` files.
- **Catalog looks empty** — click *Scan Content* and wait for the progress bar.
  First scan takes about a minute on a large Mods folder.
- **The game does not see the mod** — enable *Script Mods Allowed* in
  Options → Game Options → Other, and keep `.ts4script` no deeper than one
  subfolder in Mods.
- **Port 8765 already in use** — set `SIMSTUDIO_PORT` before starting, e.g.
  `set SIMSTUDIO_PORT=8790` then run the launcher.

---

## Project layout

```
app.py                  local HTTP server + window launcher
SimsDataSDK/            unmodified upstream SDK (src/sims4_sdk/...)
backend/sdk.py          SDK bootstrap + cached workspace/static data
backend/sdkconvert.py   SDK model -> studio JSON conversion
backend/dbpf.py         thin compatibility layer over sims4_sdk.core.dbpf
backend/protobuf.py     protobuf helpers for supplemental SDK gaps
backend/catalog.py      SDK catalog + supplemental SimData/XML scan
backend/gamedata.py     short trait conditions, compatibility filters, career/degree
                        maps, aspiration resolution, genealogy semantics
backend/templatedata.py SDK StaticData.world + premade bundle -> studio dataset
backend/premade_art.py  household composites + per-sim portrait crop rectangles
backend/saves.py        save browser via Sims4Workspace.read_save()
backend/gameicons.py    SDK tuning icons -> cached PNG (DST/DDS decoder)
backend/tray.py         Tray browser (SDK reader) + premade world seeding
backend/project.py      project storage
backend/exporter.py     .ts4script generator
backend/templates/      in-game script template
ui/                     Clean UI frontend
docs/sdk-migration.md   SDK coverage map and remaining gaps
data/catalog_cache.json scan cache (safe to delete)
data/sdk_cache/         SimsDataSDK catalog snapshot (safe to delete)
data/xml_tuning_items.json XML-only tunings merged into the catalog
data/premade_careers.json  install careers, levels and aspiration tracks
data/wiki_audit.json       per-sim wiki audit output
data/audit_report.md       readable audit summary + actionable list
data/premade_images/    cached premade household portraits (safe to delete)
data/icon_cache/        cached SDK tuning icons as PNG (safe to delete)
tools/wiki_audit.py     fetch/compare the wiki audit
tools/make_audit_report.py write data/audit_report.md
exports/                generated mods
projects/               your project file
```
