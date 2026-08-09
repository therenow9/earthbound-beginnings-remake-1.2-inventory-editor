# Start here

## First run

```bash
pip install -e ".[dev]"
pytest                       # expect 90 passed
```

Tests need no ROM and no save. The ones that want a real save skip themselves
when `saves/remake/` is empty.

## Where things stand

**Inventory editing works and is verified in the real game.** `give`, `take`,
`swap`, `equip` and `unequip` were applied to a real save, loaded in an
emulator, and confirmed two ways: every character's live inventory in the
game's RAM matched what was written byte for byte, and the Goods menu rendered
the expected items with the equip markers still on the right ones.

Re-run that check any time:

```bash
EBBR_BIZHAWK=/path/to/BizHawk python tools/ingame_verify.py \
    --rom "roms/remake/<rom>.sfc" --save "saves/remake/<save>.srm" \
    --edit "give Ninten 'Franklin badge'"
```

The item table is complete: 253 ids read out of the ROM. `data/items.json` is
committed, so regenerate only for a different build:

```bash
python tools/extract_items.py "roms/remake/<rom>.sfc" \
    --compare "roms/vanilla/EarthBound (USA).sfc"
```

## Next task: the GUI

The engine is done and verified; the remaining gap is that editing a bag from
a command line is tedious. Scope stays inventory and equipment. Full notes in
`docs/PLAN.md` under **Phase 5**, but the one thing to get right:

**Build on `Character` in `src/ebbr/sram.py`** — `add_item`, `remove_item`,
`swap_slots`, `equip_pointers` — and save through `SaveFile.edit_slot()`.
Bag contiguity, equip-pointer fixup and mirror-copy consistency are enforced
inside those, so a GUI that uses them gets correct behaviour for free and one
that writes `Character.inventory` directly quietly loses all three. The CLI is
a thin shell over exactly those calls; copy its shape.

Then check the result with `tools/ingame_verify.py`, which does not care
whether a CLI or a GUI produced the file.

## What is deliberately not done

Levels, EXP, stats, PSI, story flags and map position are unmapped and out of
scope — see `docs/PLAN.md`. Money is decoded and confirmed but not editable.

Two loose ends worth picking up:

- `hp_max`/`pp_max` (`0x48`/`0x4E`) are still INFERRED, because every save seen
  so far is at full health, making current and max indistinguishable. **One
  save taken after taking damage settles it.**
- Whatever differs between mirror copies A and B is still unidentified.

## Rules that matter

1. **Verify against two independent saves.** A renamed copy is not a second
   save — one of the files here turned out to be byte-identical to another.
2. **A fixture built from a constant cannot validate that constant.** The
   vanilla layout was wrong for the project's whole life while 44 tests passed,
   because the fixture generator sourced its geometry from the table under
   test. Pin measured values literally, as
   `test_layout_constants_match_real_saves` does.
3. **Never trust an item table that has not passed
   `items.check_against_known()`.** A base off by one record decodes to 253
   real item names, just the wrong ones. It looks completely correct.
4. **Keep bags contiguous.** The game never leaves a hole, and compacts when an
   item leaves, rewriting equip pointers to follow. Any new editing operation
   must preserve both; `test_bag_stays_contiguous_through_random_edits` is the
   guard.
5. **Never commit ROMs, patches, or personal saves.** `.gitignore` blocks
   `roms/` and `saves/` wholesale; leave those entries alone.

## Layout of local game data

```
roms/remake/     roms/vanilla/
saves/remake/    saves/vanilla/
```

Keep the two games apart. bsnes matches SRAM to ROM by filename and silently
reinitialises on a mismatch, which looks exactly like a failed edit.

If `ebbr info` reports layout `EarthBound (USA)`, that file is a vanilla save,
not a remake save — it is refused on purpose. If it errors with "contains no
saves", the SRAM is blank, which is a ROM/filename mismatch in the emulator
rather than a problem with the file.
