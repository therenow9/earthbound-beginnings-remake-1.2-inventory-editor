# Plan — inventory editor for EarthBound Beginnings Remake

## Scope

**In:** view a save, edit character inventories, set equipment.

**Out:** levels, EXP, stats, PSI, story flags, map warps, money. These need
open-ended reverse engineering with uncertain payoff. Inventory is the useful
90% and it is already understood.

Existing EarthBound editors do not work on the remake — it changed the SRAM
block geometry and reassigned the item table. (The block header layout is
unchanged; only the stride differs.) That is the gap this fills, and it does
not require replicating anything else those tools do.

## Status

**Done.** Container layer: block detection by signature scan, layout detection,
checksum validation and repair, mirror-copy consistency, automatic backups.
Character records, inventories, equipment pointers. CLI: `info`, `items`,
`give`, `equip`, `diff`. 63 tests, no ROM or personal save data required.

**Item table: done.** All 253 named ids, extracted from the ROM. `ebbr info`
now resolves every item in the test saves with no `unknown 0x..` left.

**Next:** Phase 3 usability, then release. **Optional:** GUI.

## Phase 1 — validate against real saves — DONE (partly)

Ran `ebbr info` against two real remake saves and one real stock EarthBound
save. Results:

- Both remake saves detect as EBBR, all four populated blocks checksum `ok`,
  money and party match the game.
- The vanilla save exposed a **wrong `layout.VANILLA`** — it failed to load
  entirely. Vanilla's header layout is identical to EBBR's; only stride and
  length differ. Fixed, and pinned by `test_layout_constants_match_real_saves`.

**Still outstanding:** the write round-trip. Edit a save, load it in bsnes,
confirm the change appears in-game. Nothing below is trustworthy for real use
until that is done once — every read path is now confirmed, no write path is.

Also still wanted: a save taken **after taking damage**, which would settle
`hp_max`/`pp_max` (currently INFERRED — every save so far is at full health).

## Phase 2 — item table — DONE

CoilSnake proved unnecessary. The item table is a flat array in the ROM with
the name at the start of each record, in ordinary EB text, so
`tools/extract_items.py` reads it directly:

    base 0x155000, 39 bytes per entry, name NUL-terminated, EB text (+0x30)

Established by searching for known names encoded with the bias and dividing
offset gaps by id gaps. Output is `data/items.json` — **names and ids only, no
ROM data** — loaded at CLI startup by `items.load_default()`. JSON rather than
the originally planned YAML so the package keeps zero runtime dependencies;
`items.load_yaml()` still exists for hand-maintained tables.

The extraction is gated on `items.check_against_known()` and refuses to write
on any mismatch. This is not a formality: a base off by one record yields 253
*real* item names, just shifted, and looks entirely correct.

Stock EarthBound stores its table at the same base and stride; 128 of 253
entries differ. `--compare` emits that diff.

## Phase 3 — usability

- `ebbr take` to remove an item; `ebbr swap` to reorder slots.
- Warn when giving a character an item type they may not be able to equip.
  The pendant-restriction theory is **dead**: `0x39`/`0x3A`/`0x3B` are Rain,
  Flame and Earth pendants — elemental, not per-character. They only looked
  character-specific because each party member happened to wear a different
  one. If a restriction exists it must come from the unmapped bytes in each
  39-byte ROM item record, which is where to look next.
- Better errors for the two failure modes that actually bite people: a vanilla
  save loaded by mistake, and a blank SRAM caused by a ROM/filename mismatch.
  The first is now correctly detected and refused rather than erroring out.

## Phase 4 — release

- README stating plainly: remake only, not vanilla EarthBound.
- Ship no ROM, patch, or save data.
- Consider contacting the remake team (Gabbls et al.). They may simply hand over
  the save format, or want the tool linked from the project site.

## Working rules

1. **Verify against two independent saves before believing anything.** Every
   correct conclusion in the original reverse engineering came from
   cross-validation; every wrong one came from a single-source inference.
   Note that a *copy* of a save is not a second save — one of the supplied
   files turned out to be byte-identical to another under a different name.
2. **Tag findings VERIFIED, ROM or INFERRED** in `docs/FORMAT.md` and in
   `items.py`. Do not let inferences drift into being treated as facts, and
   keep ROM-derived facts distinct from save-derived ones — `items.py` relies
   on that split to keep its cross-check from becoming circular.
3. **A fixture built from a constant cannot validate that constant.** The
   vanilla layout was wrong for the entire life of the project and 44 tests
   passed throughout, because the fixture generator read its geometry from the
   same table it was meant to be testing. Pin real measured values literally.
4. **A blank or all-zero region is not evidence.** It satisfies every
   hypothesis, including both checksums.
5. **Filenames are load-bearing.** bsnes matches SRAM to ROM by filename and
   silently reinitialises on mismatch, which looks exactly like a failed edit.
6. Back up before every write. The CLI does this automatically.
