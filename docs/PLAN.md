# Plan — inventory editor for EarthBound Beginnings Remake

## Scope

**In:** view a save, edit character inventories, set equipment.

**Out:** levels, EXP, stats, PSI, story flags, map warps, money. These need
open-ended reverse engineering with uncertain payoff. Inventory is the useful
90% and it is already understood.

Existing EarthBound editors do not work on the remake — it changed the SRAM
block geometry and header layout and reassigned the item table. That is the gap
this fills, and it does not require replicating anything else those tools do.

## Status

**Done.** Container layer: block detection by signature scan, layout detection,
checksum validation and repair, mirror-copy consistency, automatic backups.
Character records, inventories, equipment pointers. CLI: `info`, `items`,
`give`, `equip`, `diff`. 44 tests, no ROM or personal save data required.

**Blocking v1:** the item table. 18 ids known (see `src/ebbr/items.py`), most
confirmed against two independent saves. The game has far more.

**Optional after v1:** GUI.

## Phase 1 — validate against real saves

Synthetic fixtures only prove internal consistency. Run `ebbr info` on several
real saves from different points in the game and confirm money, party, HP/PP,
and inventory contents match what the game displays.

Then edit one, load it in bsnes, and confirm the change appears. Round-trip
through the actual game is the only test that matters.

## Phase 2 — item table (the blocker)

1. Install CoilSnake (`pk-hack/CoilSnake`).
2. Decompile the patched remake ROM. Decompile vanilla EarthBound too — diffing
   the two tables shows which ids were reassigned and is a free correctness check.
3. Extract item names and indices into `data/items.yml`. **Names and ids only —
   no ROM data.**
4. Run `items.check_against_known()`. It compares the import against ids
   confirmed on two independent saves. **A mismatch means the table was read
   wrong. Stop and fix it; do not proceed.**
5. Wire `items.load_yaml()` into CLI startup.

If CoilSnake cannot handle the expanded ROM, the fallback is locating the item
name table in the ROM directly and decoding EB text (ASCII + `0x30`). Slower,
same result.

## Phase 3 — usability

- `ebbr take` to remove an item; `ebbr swap` to reorder slots.
- Warn when giving a character an item type they may not be able to equip.
  Each party member carries a different pendant on sequential ids (`0x39`,
  `0x3A`, `0x3B`), which hints pendants may be character-restricted. Unconfirmed.
- Better errors for the two failure modes that actually bite people: a vanilla
  save loaded by mistake, and a blank SRAM caused by a ROM/filename mismatch.

## Phase 4 — release

- README stating plainly: remake only, not vanilla EarthBound.
- Ship no ROM, patch, or save data.
- Consider contacting the remake team (Gabbls et al.). They may simply hand over
  the save format, or want the tool linked from the project site.

## Working rules

1. **Verify against two independent saves before believing anything.** Every
   correct conclusion in the original reverse engineering came from
   cross-validation; every wrong one came from a single-source inference.
2. **Tag findings VERIFIED or INFERRED** in `docs/FORMAT.md` and in
   `items.py`. Do not let inferences drift into being treated as facts.
3. **A blank or all-zero region is not evidence.** It satisfies every
   hypothesis, including both checksums.
4. **Filenames are load-bearing.** bsnes matches SRAM to ROM by filename and
   silently reinitialises on mismatch, which looks exactly like a failed edit.
5. Back up before every write. The CLI does this automatically.
