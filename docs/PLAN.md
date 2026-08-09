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
`give`, `take`, `swap`, `equip`, `unequip`, `diff`. 90 tests, no ROM or
personal save data required.

**Item table: done.** All 253 named ids, extracted from the ROM. `ebbr info`
now resolves every item in the test saves with no `unknown 0x..` left.

**In-game verified.** Edits made by the tool load correctly in the real game;
`tools/ingame_verify.py` re-runs the check. Inventory editing is done.

**Next: the GUI (Phase 5).** The engine is finished and proven — what is left
is that driving it from a command line is not how anyone wants to edit a bag.

## Phase 1 — validate against real saves — DONE

Ran `ebbr info` against two real remake saves and one real stock EarthBound
save. Results:

- Both remake saves detect as EBBR, all four populated blocks checksum `ok`,
  money and party match the game.
- The vanilla save exposed a **wrong `layout.VANILLA`** — it failed to load
  entirely. Vanilla's header layout is identical to EBBR's; only stride and
  length differ. Fixed, and pinned by `test_layout_constants_match_real_saves`.

- The write round-trip is done, and automated rather than manual.
  `tools/ingame_verify.py` injects an edited save into BizHawk, loads it, and
  compares every character's live inventory in WRAM against what was written.
  A compound edit (take + give + swap + equip across two characters) came back
  byte-exact on all four bags, with the Goods menu rendering correctly.

Still wanted: a save taken **after taking damage**, which would settle
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

## Phase 3 — usability — MOSTLY DONE

- `ebbr take` and `ebbr swap` exist, as do `unequip` and `--dry-run`, and any
  bag slot can be given as an item name instead of a number. Both editing
  operations maintain the two invariants the game maintains: bags stay
  contiguous, and equip pointers follow the items they point at.
- Warn when giving a character an item type they may not be able to equip.
  The pendant-restriction theory is **dead**: `0x39`/`0x3A`/`0x3B` are Rain,
  Flame and Earth pendants — elemental, not per-character. They only looked
  character-specific because each party member happened to wear a different
  one. If a restriction exists it must come from the unmapped bytes in each
  39-byte ROM item record, which is where to look next.
- Better errors for the two failure modes that actually bite people: a vanilla
  save loaded by mistake, and a blank SRAM caused by a ROM/filename mismatch.
  The first is now correctly detected and refused rather than erroring out.

## Phase 5 — GUI — NEXT

The one thing standing between this and something pleasant to use. Scope stays
inventory and equipment: open a save, see the four bags, move items around,
save.

**Build it on the existing model, not beside it.** Everything the GUI needs is
already on `Character` in `src/ebbr/sram.py`:

| want | call |
|---|---|
| add | `add_item(item_id, slot=None)` |
| remove | `remove_item(slot)` |
| reorder | `swap_slots(a, b)` |
| equip | `equip_pointers` |
| look up | `items.name()` / `items.find()` |

This matters more than it sounds. Bag contiguity and equip-pointer fixup are
enforced *inside* those methods, so a GUI that calls them inherits correct
behaviour, while one that assigns to `Character.inventory` directly silently
loses both. The CLI is a thin shell over the same calls — copy its shape.

Two rules a GUI must not skip:

1. **Write through `SaveFile.edit_slot()`.** It applies the change to both
   mirror copies and re-checksums each. Writing a block directly produces a
   file that half-loads.
2. **Back up before saving**, as `cli._backup()` does.

Suggested shape:

- tkinter. It is in the stdlib, which keeps the zero-dependency promise; a
  four-column list of bags with add/remove/reorder does not need more.
- Call `items.load_default()` once at startup, as the CLI does.
- A searchable item picker matters: there are 253 ids and the names collide
  ("bat" matches 15). Reuse `items.find()` and the exact-match rule in
  `cli._resolve_item()`.
- Refuse non-EBBR saves up front — `cli._load_editable()` already does this.

Verify GUI edits the same way as CLI edits: save, then run
`tools/ingame_verify.py` against the result. It compares the game's live
inventory, so it does not care which front end produced the file.

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
