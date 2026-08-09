# Start here

## First run

```bash
pip install -e ".[dev]"
pytest                       # expect 63 passed
```

Reading a save needs nothing else. Regenerating the item table needs a ROM:

```bash
python tools/extract_items.py "roms/remake/<your rom>.sfc" \
    --compare "roms/vanilla/EarthBound (USA).sfc"
```

`data/items.json` is committed, so this is only necessary for a different
remake build.

## Where things stand

Reading is done and confirmed against real saves — container geometry, both
layouts, character records, inventories, equipment, and all 253 item names.
`ebbr info` on a real remake save resolves every item with no `unknown 0x..`.

**Writing has never been proven.** No edit has been round-tripped through the
game. That is the next task, and nothing should be called v1 until it is done:

```bash
ebbr give <save> Ninten "Magic coin"
```

then load the save in bsnes and confirm the item is actually there. If it is
not, suspect the mirror-copy handling in `SaveFile.edit_slot()` first.

Also wanted: **a save taken after taking damage.** Every save examined so far is
at full health, so `hp_max`/`pp_max` at `0x48`/`0x4E` cannot be distinguished
from current HP/PP and remain INFERRED.

Read `docs/PLAN.md` for the roadmap and `docs/FORMAT.md` for the format.

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
4. **Never commit ROMs, patches, or personal saves.** `.gitignore` blocks
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
