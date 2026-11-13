# SimsDataSDK migration

The upstream SDK is cloned, unmodified, in **`SimsDataSDK/`**:

```
SimsDataSDK/            # git clone of scayze/SimsDataSDK
  src/sims4_sdk/...
```

`backend/sdk.py` is the only place that adds `SimsDataSDK/src` to `sys.path`.
It builds and caches a `Sims4Workspace` against the detected game/user folders
and exposes the shared `StaticData` / `Catalog` objects to the rest of the
studio. The SDK's own cache lives in `data/sdk_cache/`.

## What is replaced

| Studio code | Now backed by |
| --- | --- |
| `backend/dbpf.py` | `sims4_sdk.core.dbpf.DBPF` (index parsing, compression IDs, RefPack/zlib) |
| `backend/refpack.py` | `sims4_sdk.core.refpack` |
| `backend/protobuf.py` | small supplemental wire parser (names only); all save/Tray decoding is SDK |
| `backend/saves.py` | `Sims4Workspace.read_save()` → full `SavedSim`, households, zones, traits, likes/dislikes, careers, skills, milestones, genealogy, **save artwork and alpha masks** |
| `backend/catalog.py` | `Catalog` for traits, preferences, aspirations/tracks, careers/tracks, milestones and relationship bits; the local scan is limited to the definition kinds the SDK does not model |
| `backend/templatedata.py` | `StaticData.world` + `StarterHouseholdRecord` + `PremadeBundle`, typed `parent_links`/`child_links`/`sibling_links`, `PremadeBundle.family_tree()`, `Catalog.family_fixups` and `Catalog.premade_relationships`; no duplicate package scan |
| `backend/premade.py` | **removed** |
| `backend/simdata.py` | **removed**; the SDK now decodes all 590 local `.householdbinary` files |
| `backend/households.py` | reduced to the name resolver used by supplemental datasets |
| `backend/setups.py` | **removed**; replaced by `Catalog.premade_relationships` |
| `backend/tray.py` | `read_household_binary()` and the new `TrayLibrary.errors` handling |
| `backend/images.py` | `sims4_sdk.save.artwork` for decoding and PNG conversion; wrapper and JPEG/mask fallbacks remain for unsupported Tray images |
| `backend/premade_art.py` | `sims4_sdk.core.dbpf.DBPF` and `save.artwork.decode_artwork()` for household composite masks |
| `backend/gameicons.py` | `Sims4Workspace.icon_for()` + `GameImage.to_png()`; local DXT→PNG conversion remains as a fallback |

The studio still owns UI-facing enrichment: compatibility labels, career branch
rules, aspiration track labels, relationship labels, dynasties, secrets, clubs,
EP21 NPC setup tunings, the exporter and the project file.

## Remaining gaps after the upstream update

### 1. Household member names stored as STBL keys

Some `0xB3C438F0` members store `first_name`/`last_name` as STBL keys
(`fields 55/56`) instead of inline strings. The SDK leaves those names empty;
without resolving them 384 of 434 world members have no name and several
households cannot be matched to their tuning template.

**Local workaround:** `backend/templatedata.py::_read_names()` reads the two keys
from `StarterHouseholdRecord.raw` and resolves them through `Catalog.strings`.

**Requested:** `StarterMember.first_name_key` / `last_name_key`, or resolve them
in `parse_premade_household()` using the catalog string table.

### 2. Skill levels are still raw XP

`SkillLevel` / `SavedSkill` expose `value` but `level` is `None`.
The studio still computes levels with its own curve
(`backend/skillcurve.py`: adult, child, toddler and Vampire Lore curves).

**Requested:** `SkillLevel.level` (or a public `skills.level_for(skill_id, xp)`
helper) using the game curves.

### 3. Pre-made template fields still missing

`PremadeSim` still does not expose:

- `PremadeSimTemplate.clubs` and club seed names.
- `SimInfoFixup` / `secrets_fixup_action` premade scandal secrets.
- `DynastySeed` name and description (`PremadeSim.dynasty` contains only the
  seed id and head/heir/black-sheep flags).
- `TunablePremadeAncestor` title, region/noble rank and other tapestry metadata
  (the typed family-tree links, thumbnails and death traits are now provided).
- `_fixups` starting developmental milestones.
- Structured gender identity / pronoun set. `pronouns` is a raw string, and
  `gender` / `gender_options.frame` do not distinguish a non-binary identity
  from the physical frame.
- A normalized display name for **Sims**. (Household `display_name` is now
  available and used.)

**Requested:** `club_ids`, `secrets`, `dynasty_seed`/`dynasty_description`,
ancestor titles/regions, `fixup_milestone_ids`, `pronoun_set` /
`gender_identity`, and `PremadeSim.display_name`.

### 4. Catalog definition kinds still missing

The studio still supplements the SDK catalog for:

- **Skill / Statistic** — no model, display name, icon, pack, age/species or
  occult restrictions.
- **Degree** — the game stores degrees as `trait_University_*` traits.
- **Identity** — `trait_adult`, `trait_Gender*`, `trait_Species_*`,
  `trait_Occult_*`.
- **Occult** — `OccultTrait` / `OccultTrackerItem`.
- **Objective** — `Objective` tunings, needed to resolve a track to a specific
  aspiration.
- **RelationshipTrack** — only `RelationshipBit` and default track values are
  modelled.

Also still local:

- `AspirationTrack.track_display_name` (the SDK’s `display_name` is the linked
  aspiration, e.g. “Party Animal”, not “Popularity C”).
- Pack display names (`Catalog` exposes codes such as `BASE`, `EP12`; the studio
  maps them through `PACK_NAMES`).

Now provided by the SDK and in use: `Trait.icon_key`/`has_icon`,
`Aspiration`/`Milestone`/`RelationshipBit` icon keys,
`Sims4Workspace.icon_for()` / `icon_bytes()` / `icon_png()`,
`sims4_sdk.core.images` (DST/DDS unshuffling), `Trait.is_internal`,
`Catalog.visible_traits`, `Career.display_name`, `PremadeHousehold.display_name`,
`PremadeHousehold.description`, `PremadeHousehold.lot_ids`,
`PremadeSim.fiance_id`/`steady_ids`/typed kinship links,
`PremadeBundle.family_tree()` / `FamilyTree.ancestors_of()`,
`Catalog.family_fixups`, `Catalog.diagnostics` / `ExtractionIssue`.

### 5. Save relationships and skill levels

Some saves still return an empty `SavedSim.relationships` list even though the
relationship tracker exists in the payload (for example `Slot_00000018.save` /
Bella Goth). The studio cannot show friendship/romance scores or bits for those
saves.

**Requested:** a complete per-Sim relationship decode for saves and Tray.

### 6. Save/Tray artwork wrapper variants

Save artwork, `SaveFile.thumbnail`, `household_artwork`, Tray
`household_image()` / `portrait()` and `Artwork.alpha_mask` are now available
and used.

One gap remains: `read_tray_image()` rejects **178 of 2,772** local `.hhi`/`.sgi`
files because their 16-byte wrapper marker differs from the expected
`8efc24489b780e3c0200000000000000`. The old XOR wrapper still reads them.

**Requested:** accept wrapper variants (the length field at bytes 0–3 matches
`len(data) - 24`; bytes 8–15 are the same marker; bytes 16–23 differ).

### 7. `SimInfo` is still trait-only

`SimInfo` reads the baked trait list but not likes/dislikes, degrees,
aspiration, career or skills. The studio gets most of these from
`PremadeSimTemplate` / household resources instead.

**Requested:** parse the remaining SimInfo sections.

### 8. Premade household composite portraits

The game ships a transparent-background group portrait per premade household as
resource type `0x3BD45407`. The SDK does not expose it yet; the studio still
scans packages and extracts the largest JPEG plus its `ALFA` mask in
`backend/premade_art.py`.

**Requested:** `PremadeBundle.portrait(template_id) -> Artwork | None`.

### 9. Write/export support

The SDK is read-only. `backend/exporter.py` and project storage remain local.
If the SDK is meant to replace all backend functionality, it needs a
script-mod/package writer or documented export hooks. Otherwise this is out of
scope.

## Verification

Verified against the local install (`D:\Spellen\The Sims 4`) and user folder:

- SDK `0.9.0` (`8b9793d6a601d001d1e82b3b4ef0004eb7f32311`, “Add PNG
  conversion for icons and artwork”; full clone with history).
- SDK static data: 2,801 traits, 334 preferences, 392 aspirations, 146 careers,
  671 career levels, 201 milestones, 769 relationship bits; 431 premade Sims /
  204 households / 41 ancestors / 548 lots; **207** household resources and
  0 diagnostics.
- Catalog: `traits=518, skills=90, careers=146, career_tracks=203,
  aspirations=204, aspiration_tracks=106, milestones=201, preferences=428,
  degrees=69, identity=18, objectives=1866, relationship_bits=769,
  relationship_tracks=32`.
- Clean-world dataset: **200 households / 425 Sims**, 1,821 likes, 673 dislikes,
  1,078 skills, 902 relationship bits, 348 cross-household relationships,
  58 cross-household family links and 41 Sims with SDK-derived ancestor lists.
- Tray: all **590** `.householdbinary` files decode (SDK), 590 households in the
  library with 0 errors, 541 listed by the studio.
- Save `Slot_00000018.save`: 431 Sims / 184 households / 377 artwork images,
  0 artwork errors.
- Tray images: 2,772 JPEGs and 2,714 alpha masks decode through the SDK plus the
  wrapper fallback.
- Tuning icons: SDK resolves all 2,801 trait icons and the studio catalog carries
  1,891 icon keys across traits, aspirations, careers, milestones and
  relationship bits. `backend/gameicons.py` decoded all 1,891 to cached PNGs
  (DXT1, DXT5 and uncompressed 32-bit DDS; `trait_Mean` renders correctly).
