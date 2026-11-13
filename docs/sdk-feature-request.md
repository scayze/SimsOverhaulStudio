# Make SimsDataSDK the sole extraction backend for Sim Overhaul Studio

**Repository:** `scayze/SimsDataSDK`
**Version tested:** `0.9.0` (`60245cf355ed4b85f837afc1ea9052fdcf2fdec2`)

> **Status after upstream update `8b9793d6a601d001d1e82b3b4ef0004eb7f32311`:**
> package discovery, the Tray `TypeError`, household relationships /
> milestones / fiancé / steady / occult / degree fields, save and Tray artwork,
> household display names/descriptions/lot links, tuning icon extraction
> (DST/DDS + PNG), typed family-tree links / ancestors / family fixups,
> `Career.display_name`, `Trait.is_internal` / `Catalog.visible_traits` and
> structured diagnostics are now implemented. Remaining requests: STBL-keyed
> member names, skill levels, clubs/secrets/dynasty/ancestor titles/pronoun
> data, the supplemental catalog kinds and aspiration-track label, complete
> save relationship decoding, Tray wrapper variants, further `SimInfo`
> sections, premade composite portraits and optional write support.

## Context

I maintain **Sim Overhaul Studio**, a local, read-only Body Shop–inspired desktop
app for *The Sims 4*. It lets a user:

- browse saves and the Tray library;
- inspect clean new-save premade households (traits, likes/dislikes, skills,
  careers, aspirations, degrees, milestones, relationships, dynasties);
- edit those values and export a `.ts4script` overhaul mod;
- never writes into the game install, saves or Tray folder.

The app is Python (stdlib only) with a local HTTP/UI layer. All Sims 4 data
extraction currently lives in `backend/`, and I have vendored **SimsDataSDK
0.9.0** (`60245cf355ed4b85f837afc1ea9052fdcf2fdec2`) as the new backend.

The SDK already replaced a lot of fragile local code:

- DBPF index/compression readers (`core.dbpf`, `core.refpack`);
- save parsing (`Sims4Workspace.read_save()`);
- Tray parsing (`save.tray`);
- the static catalog for traits, preferences, aspirations/tracks, careers,
  career tracks, milestones and relationship bits;
- premade template/household/lot/ancestor extraction;
- cross-household starting relationships (`PremadeSimRelationships`).

The goal of this issue is to close the remaining gaps so the studio can **delete
its supplemental parsers and derived JSON datasets** and use the SDK as the only
source of game data.

Environment used for the evidence below: Windows, Python 3.15, base game + all
installed packs, ~590 Tray household binaries, 16 saves, ~6,900 packages.

---

## Current blockers

### 1. Tray reader raises `TypeError` on valid Tray files

`read_household_binary()` fails on `.householdbinary` files where a `float` or
`double` field is encoded as a varint:

```
TypeError: object of type 'int' has no len()
  at sims4_sdk/save/protobuf.py:172 _scalar_or_packed()
```

On my Tray folder this affects **191 of 590** files. `read_tray_library()` only
catches `TrayError`, so a single such file aborts the entire library instead of
returning the other 399 households.

**Requested**

- Make `_scalar_or_packed()` tolerate varint values for `float`/`double`
  (coerce to `float(value)`), or treat an unexpected wire type as a skipped
  field instead of a hard failure.
- Make `read_tray_library()` catch all per-file exceptions, keep going, and
  optionally expose the failures:
  ```python
  library = read_tray_library(folder)
  library.errors  # [{"path": ..., "error": ...}, ...]
  ```
- Add a regression fixture with a varint-encoded float field.

**Acceptance:** all 590 local `.householdbinary` files either decode or are
reported in `library.errors`; `read_tray_library()` never aborts.

---

### 2. `Installation.packages` misses game packages

The SDK currently discovers only part of the retail install:

- `Installation.base_packages` includes `Data/Client/ClientFullBuild0.package`
  and `ClientDeltaBuild0.package`, but **not** `ClientFullBuild1..8.package` or
  `ClientDeltaBuild1..8.package`.
- `Installation.pack_packages` walks `Delta/<PACK>`, but **not**
  `<PACK>/ClientFullBuild0.package` at the pack root.

Those packages contain many `0xB3C438F0` premade household resources and the
household composite portraits. With the current discovery the SDK sees **177**
unique household resources; scanning the missing packages finds **207**.

**Requested**

- Include every game package in `Installation.packages`:
  - `Data/Simulation/*.package`
  - `Data/Client/*.package`
  - `Delta/<PACK>/*.package`
  - `<PACK>/*.package` (pack root)
- Keep mods last in load order.
- Or expose a documented extension point, e.g.
  `Sims4Workspace(..., extra_packages=[...])` / `build_static(..., packages=...)`,
  so callers can add packages without reimplementing discovery.

**Acceptance:** on my install, `len(Installation.packages)` includes those
packages and `collect_world_data()` returns 207 unique `0xB3C438F0` records.

---

## Premade data gaps

### 3. `0xB3C438F0` household resource fields

`WorldData.StarterMember` exposes names, gender/age flags, `trait_ids`, raw
skill values, careers, spouse id and genealogy. The studio still has to decode:

| Field | What it contains | Currently local |
| --- | --- | --- |
| `gameplay.1` | per-Sim relationship tracker: target id, relationship bits, sentiments, friendship/romance track values | yes |
| `field 47.27` | developmental milestones (and completed state) | yes |
| `field 68` | fiancé id | yes |
| `field 72` | steady partner ids | yes |
| `gameplay.17` | occult tracker | yes |
| `gameplay.30` | degree tracker | yes |
| skill values | raw XP only; no level | yes (`skillcurve.py`) |
| household header | description / lot linkage (the lot manifest has keys) | partly |

**Requested models**

```python
@dataclass
class StarterRelationship:
    target_id: int
    bit_ids: list[int]
    sentiment_ids: list[int]
    tracks: list[RelationshipTrackValue]  # friendship/romance/etc.

@dataclass
class StarterMember:
    ...
    fiance_id: int | None
    steady_ids: list[int]
    relationships: list[StarterRelationship]
    milestones: list[StarterMilestone]
    occult: list[str]
    degrees: list[int]
    skills: list[SkillLevel]          # with level, not only value
    career_history: list[StarterCareer]

@dataclass
class StarterHouseholdRecord:
    ...
    description: str | None
    lot_id: int | None
```

Also expose `SkillLevel.level` using the game's XP curves (adult, child,
toddler, Vampire Lore). If the curve table is out of scope, expose a public
helper such as `sims4_sdk.skills.level_for(skill_id, xp)`.

**Acceptance:** the studio can delete its household-template supplemental
decoder and `skillcurve.py` reliance for premades; Bella Goth decodes as
Charisma/Fitness/Programming 2 and her spouse/family tracker matches the raw
resource.

### 4. `PremadeSimTemplate` fields

Still missing from `PremadeSim`:

- `clubs` (`PremadeSimTemplate.clubs`) and club seed names.
- `SimInfoFixup` / `secrets_fixup_action` premade scandal secrets.
- `DynastySeed` name and description. `PremadeSim.dynasty` only has
  `{seed, is_head, is_heir, is_black_sheep}`; the seed tuning name/description
  is not exposed.
- Ancestor tapestry metadata: `TunablePremadeAncestor` title, region/noble
  rank, and other fields beyond `full_name`, `gender`, `death_trait_id`,
  `thumbnail`.
- `_fixups` starting developmental milestones.
- Structured gender identity and pronoun set. `pronouns` is a raw string and
  `gender`/`gender_options.frame` cannot distinguish a non-binary identity from
  the physical frame.
- Normalized household display names. `PremadeSim.name` and
  `PremadeHousehold.name` are tuning names (`premadeSimTemplate_BellaGoth`,
  `premadeHouseholdTemplate_Goth`).

**Requested**

```python
PremadeSim.club_ids: list[int]
PremadeSim.secrets: list[PremadeSecret]
PremadeSim.dynasty_seed: DynastySeed | None      # name + description
PremadeSim.fixup_milestone_ids: list[int]
PremadeSim.pronoun_set: PronounSet | None
PremadeSim.gender_identity: str | None
PremadeHousehold.display_name: str | None
PremadeAncestor.title: str | None
PremadeAncestor.region: str | None
PremadeAncestor.rank: str | None
```

**Acceptance:** the studio can drop `premade_clubs.json`,
`premade_secrets.json`, `premade_dynasties.json`, `premade_milestones.json` and
the `gender_identity`/`pronouns` overlay from `premade_careers.json`.

---

## Catalog gaps

### 5. Missing definition kinds

The studio catalog needs these kinds, which the SDK does not model yet:

| Kind | Current local extraction | Requested model |
| --- | --- | --- |
| Skills | SimData token scan (`Skill` / `Statistic`) | `Skill` / `Statistic`: id, name, display_name, icon, pack, ages, species, occult restrictions, skill curve type |
| Degrees | `trait_University_*` traits | `Degree`: id, name, display_name, major, level/honours, icon |
| Identity | `trait_adult`, `trait_Gender*`, `trait_Species_*`, `trait_Occult_*` | `IdentityDefinition` with kind/value |
| Occults | `OccultTrait` / `OccultTrackerItem` | `Occult` model |
| Objectives | `Objective` tunings | `Objective`: id, name, display_name, aspiration track links |
| Relationship tracks | `RelationshipTrack`, object/short-term tracks | `RelationshipTrack`: id, name, display_name, range/bit data |
| Career levels | SDK has `CareerLevel`, but the studio still resolves some names locally | expose `Career.display_name` and level display names consistently |

Also useful:

- `Trait.icon` is a raw resource-key string; a decoded icon/thumbnail API would
  replace the studio's icon-pack heuristics.
- `Career` has no `display_name` (only `CareerTrack` does).
- `AspirationTrack.display_name` is the linked aspiration name (“Party Animal”),
  not the track label (“Popularity C”). Add
  `AspirationTrack.track_display_name`.
- Expose pack display names alongside codes (`BASE` → “Base Game”, `EP12` →
  “High School Years”).
- Add a “visible/assignable” view: the catalog currently includes degree traits,
  gender options and preferences-as-traits in `Catalog.traits`; a
  `Catalog.visible_traits` / `is_internal` flag would let UIs stop re-filtering.

**Acceptance:** the studio can delete its supplemental SimData scanner and
`data/xml_tuning_items.json` merge; catalog counts and labels come entirely from
the SDK.

---

## Save / Tray gaps

### 6. Save and Tray model completeness

- `SavedSkill.level` is always `None`; only raw `value` is exposed.
  Add `level` (using the game curve) or a public conversion helper.
- Some saves return an empty `SavedSim.relationships` list even though the
  relationship tracker exists in the payload. Currently the studio cannot show
  friendship/romance scores or bits for those saves.
- `SimInfo` intentionally reads only the trait list. The studio still needs
  likes/dislikes, degrees, aspiration, career and skills baked into `SimInfo`.
- Tray/save artwork is not exposed:
  - save thumbnail / household JPEG resources;
  - Tray `.sgi` sim portraits and `.hhi` household images;
  - embedded `ALFA`/`ALFJ` mask data;
  - household composite thumbnails (`0x3BD45407`).
- `TrayHousehold` lacks lot/description metadata beyond
  `family_name`/`description`.

**Requested**

```python
SavedSkill.level: int | None
SavedSim.relationships: list[SavedRelationship]   # always populated when present
SimInfo: traits, preferences, aspiration, career, skills, degrees
SaveFile.thumbnail: bytes | None
SaveFile.household_artwork: dict[int, bytes]
TrayHousehold.portrait(sim_id) / household_image()
TrayImage: jpeg bytes + alpha mask
```

**Acceptance:** the studio can drop `backend/skillcurve.py` level computation,
the Tray artwork decoder (`backend/images.py`) and the save JPEG scan.

---

## Asset / thumbnail gap

### 7. Household composite portraits

The game ships a transparent-background group portrait for every premade
household as resource type `0x3BD45407`, keyed by household template instance.
The studio still scans packages and extracts the largest JPEG with an embedded
`ALFA`/`ALFJ` mask, then derives per-sim crop rectangles.

**Requested**

- `PremadeBundle.portrait(template_id) -> bytes | None`
- A decoded image object exposing `jpeg` and `alpha_mask`.
- Optional: `portrait_crops` helper. (The crop heuristic itself may stay local.)

**Acceptance:** the studio can drop `backend/premade_art.py`'s package scan and
mask decoder.

---

## Write/export support (optional / scope question)

The SDK is read-only. The studio's `.ts4script` exporter
(`backend/exporter.py`) and project storage remain local. If “replace all
backend functionality” includes writing, the SDK would need at minimum:

- a script-mod/package writer,
- validation of generated tuning/package references,
- or a documented “export hooks” API so external exporters can rely on SDK
  models rather than raw JSON.

If write support is intentionally out of scope, that is fine — I will keep the
exporter local, but it would be useful to state this explicitly in the SDK
README.

---

## Suggested implementation order

1. Tray varint/float tolerance + per-file error handling (**blocker**).
2. Complete package discovery (**blocker** for premade completeness).
3. `0xB3C438F0` relationships/milestones/skills fields (**replaces biggest local decoder**).
4. `PremadeSimTemplate` clubs/secrets/dynasty/pronouns (**replaces JSON datasets**).
5. Catalog `Skill`/`Degree`/`Identity`/`Objective`/`RelationshipTrack` models (**replaces supplemental scanner**).
6. Save/Tray levels, relationships and artwork.
7. Household composite portraits.
8. Optional writer/export hooks.

## Local evidence / validation

Current SDK static build on this install:

```
Catalog(traits=2793, preferences=334, aspirations=392, careers=146,
        career_levels=671, milestones=201, relationship_bits=766)
premades: 431 sims / 204 households / 41 ancestors / 548 lots
```

Current studio catalog after SDK + supplemental kinds:

```
traits=518, skills=90, careers=146, career_tracks=203, aspirations=204,
aspiration_tracks=106, milestones=201, preferences=428, degrees=69,
identity=18, objectives=1866, relationship_bits=766, relationship_tracks=32
```

Clean-world dataset:

```
200 households / 425 sims
1,821 likes / 673 dislikes
1,078 skills / 764 relationship bits / 348 cross-household relationships
```

Good regression checks:

- Bella Goth: Charisma/Fitness/Programming 2, Secret Agent 2, Popularity C,
  Romantic/Good/Family-Oriented/Gregarious.
- Tybalt Capp: Painting 8 / Piano 6 / Swordsmanship 7 / Charisma 9.
- Travis Scott (BFF): Programming 2 / Video Gaming 2; the 100 XP skill floor
  must not appear as 19 assigned skills.
- Save `Slot_00000018.save`: 431 sims / 184 households, with artwork.
- Tray library: 541 listed households; all 590 files should decode or be
  reported individually.

## Checklist

- [x] Tray reader tolerates varint floats and never aborts the library.
- [x] `Installation.packages` includes all base client and pack-root packages.
- [x] `StarterMember` exposes relationship tracker, milestones, fiancé/steady,
  occult/degrees and household description/lot links.
- [ ] `StarterMember` skill levels (raw XP only) and STBL-keyed first/last names.
- [ ] `PremadeSim` exposes clubs, secrets, dynasty seed, ancestor titles,
  fixup milestones, structured pronouns/gender identity and display names.
- [x] `Career.display_name`, `Trait.is_internal`, `Catalog.visible_traits` and
  structured extraction diagnostics.
- [x] Tuning icon keys and `Sims4Workspace.icon_for()` / DST/DDS image
  extraction.
- [x] Typed family-tree links, ancestor nodes, `FamilyTree` and
  `Catalog.family_fixups`.
- [ ] Catalog models for Skill, Degree, Identity, Occult, Objective and
  RelationshipTrack; aspiration track label and pack labels.
- [x] Save and Tray artwork, including alpha masks and save thumbnails.
- [ ] Saved/Tray skill levels and complete relationship data.
- [ ] Remaining Tray image wrapper variants (178 of 2,772 local images).
- [ ] Premade household composite portraits (`0x3BD45407`).
- [ ] Further `SimInfo` sections (likes/dislikes, degrees, aspiration, career,
  skills).
- [ ] Write/export support is either implemented or explicitly declared out of
  scope.
