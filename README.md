# EBBR Save Editor

A save editor for **EarthBound Beginnings Remake**, the SNES ROM hack that
rebuilds Mother 1 inside EarthBound's engine.

Existing EarthBound save editors do not work on it. The remake changed the SRAM
block geometry and reassigned the item table, so a vanilla editor will either
refuse the file or corrupt it. (The block *header* layout is unchanged — data
still starts at `+0x20` with checksums at `+0x1C`/`+0x1E`. Only the stride
differs, `0x550` against vanilla's `0x500`, which is enough to break everything
downstream.)

> ⚠️ Experimental. Always keep a backup. The tool writes one automatically, but
> a bad edit can still cost you a save.

## Status

**Scope: inventory, equipment and character stats.** Not PSI, the melody
counter, story flags or map warps — those are still unmapped, and guessing at
them is how save editors corrupt files.

Working: container handling (block detection, checksum validation and repair,
mirror-copy consistency), character records, inventories, equipment, HP, PP,
level, experience, the seven base stats, and money — through a GUI or a CLI.

The item table is complete: all 253 named ids, read straight out of the ROM by
[tools/extract_items.py](tools/extract_items.py). You supply your own ROM; the
repo ships names and ids only.

**Editing is verified in the actual game.** `give`, `take`, `swap` and `equip`
were applied to a real save, loaded in an emulator, and checked two ways: every
character's live inventory in the game's RAM matched what was written, byte for
byte, and the Goods menu showed the expected items with the equip markers still
on the right ones. [tools/ingame_verify.py](tools/ingame_verify.py) re-runs that
check on demand.

## Install

**Just want to edit a save?** Download `EBBR-Save-Editor.exe` from the
[latest release](../../releases/latest) and run it. Nothing to install, and
**no ROM needed** — the editor only ever opens your `.srm`, and all 253 item
names are built into the executable. A ROM is only required to regenerate the
item table from source.

From source:

```bash
git clone <your-repo-url>
cd ebbr-save-editor
pip install -e ".[dev]"
```

Python 3.10+. No required runtime dependencies.

## The GUI

```bash
ebbr-gui              # or: ebbr-gui save.srm
```

Pick a save slot, pick a character, edit their bag. `Add…` opens a
search-as-you-type item picker; `Remove` and the arrows reorder. Equipment is a
dropdown per slot, listing only what that character is carrying *and* can wear
there — a hamburger is never offered as a weapon. HP, PP, level, experience,
the seven base stats and money are editable in place, with current HP/PP capped
at their maxima. A `.bak` is written on every save.

To build the standalone executable:

```bash
python packaging/build_exe.py     # -> dist/EBBR-Save-Editor.exe
```

## Use

```bash
ebbr info save.srm                            # summarise slots, party, bags
ebbr items                                    # list every known item id
ebbr items pendant                            # search

ebbr give save.srm Ninten "Goddess band"      # append to the bag
ebbr give save.srm Teddy 0xE6 --slot 3        # insert at slot 3, push the rest down
ebbr take save.srm Ninten Hamburger           # remove by name...
ebbr take save.srm Ninten 6                   # ...or by bag slot
ebbr swap save.srm Ninten 0 3                 # reorder two slots

ebbr equip save.srm Teddy weapon "Silver sword"
ebbr unequip save.srm Teddy body

ebbr diff a.srm 0 0 --file-b b.srm            # field-named byte diff
```

Anywhere a bag slot is wanted you can give an item name instead of a number.
Every editing command takes `-n`/`--dry-run` to show what would change without
writing, `--save-slot` to pick a save slot other than the first, and writes a
`.bak` beside the file unless you pass `--no-backup`.

The equip slots are **weapon, body, arms, other** — the game's own names. An
item is only accepted in the slot its ROM item-type says it belongs to, so
`equip ... weapon Hamburger` is refused rather than written. The older names
`pendant`, `band` and `coin` still work as aliases for `body`, `arms` and
`other`.

Bags stay contiguous the way the game keeps them: `give --slot` inserts and
pushes the rest down rather than overwriting, `take` closes the gap, and both
rewrite the equip pointers so equipped gear stays equipped. `diff` translates
offsets into field names where they are known, which is what makes mapping new
fields tractable.

## Finding your save

Emulators name SRAM after the ROM. If your ROM is `EBBR.sfc`, the save is
`EBBR.srm` beside it or in the emulator's save directory.

**Filenames are load-bearing.** bsnes matches SRAM to ROM purely by filename and
silently reinitialises the file when it does not match — which looks exactly
like "my edit did not work." Keep the remake ROM in its own folder, away from
vanilla EarthBound, and close the emulator fully before swapping files, since
SRAM is flushed on exit.

## Development

```bash
pytest
```

Tests generate their own synthetic saves via `tools/make_fixture.py`, so no ROM
or personal save data is needed — and none should ever be committed. The
`.gitignore` blocks ROM and save extensions; leave those entries in place.

The most important test is `test_roundtrip_is_byte_identical`: load a save,
write it back with no edits, and require the output to equal the input byte for
byte. If that fails, nothing else can be trusted.

Second most important is `test_layout_constants_match_real_saves`, which pins
the geometry to literal measured values. The other layout tests build their
fixtures *from* those constants, so they stay green even when the constants are
wrong — which is exactly how the vanilla layout stayed broken through a fully
passing suite.

### Proving an edit works in the real game

Tests cannot tell you the *game* accepts what was written.
[tools/ingame_verify.py](tools/ingame_verify.py) can: it applies edits through
the real CLI, injects the result into an emulator, loads the save, and compares
each character's live inventory in the game's RAM against what we wrote.

```bash
export EBBR_BIZHAWK=/path/to/BizHawk        # or pass --bizhawk
python tools/ingame_verify.py \
    --rom "roms/remake/EarthBound Beginnings 1.2 (USA).sfc" \
    --save "saves/remake/your.srm" \
    --edit "take Ninten Hamburger" \
    --edit "give Ninten 'Franklin badge'" \
    --edit "swap Ninten 0 3"
```

Needs [BizHawk](https://tasvideos.org/BizHawk) for its Lua API; a window opens
for a few seconds while it runs. It also drops screenshots of the Goods menu,
which is worth a look — the automated check compares bytes, but only your eyes
confirm the game *renders* what you meant.

The save is injected straight into the emulator's SRAM rather than copied into
BizHawk's save directory, so it neither depends on nor disturbs your emulator
setup, and your real saves are never touched.

### Local ROMs and saves

Not committed, and ignored wholesale by directory:

```
roms/remake/    roms/vanilla/
saves/remake/   saves/vanilla/
```

Keeping the two games apart matters beyond tidiness: bsnes matches SRAM to ROM
by filename, so a remake save sitting next to vanilla EarthBound is a way to
silently reinitialise it. Regenerate the item table after adding a ROM:

```bash
python tools/extract_items.py "roms/remake/<rom>.sfc" \
    --compare "roms/vanilla/EarthBound (USA).sfc"
```

## Reporting a bug

[Open an issue.](../../issues) Three things account for most reports and none
is a bug: a vanilla EarthBound save being refused, a blank SRAM from a
ROM/filename mismatch, and an edit "not working" because the emulator was still
open and overwrote the file on exit.

Worth including: what you did, what happened versus what you expected, the
editor and EBBR versions, and your `.srm` if you are willing — nearly every
report is reproducible in seconds with the file and guesswork without it.

**Never attach a ROM or a patch.** This project ships no game data and cannot
accept any. A save file alone is fine.

Note that Offense and Defense are recalculated by the game on any equipment
change, and maximum HP/PP change on level-up, so the editor and the game
disagreeing on those is expected. Anything else should match exactly.

## Contributing format findings

Mark every entry in `docs/FORMAT.md` as **VERIFIED**, **ROM** or **INFERRED**,
and say what established it. Verified means confirmed against two or more
independent saves; ROM means read out of the ROM itself. This distinction
matters more than it sounds: every wrong conclusion during the original reverse
engineering came from a single-source inference stated with too much confidence.

Keep ROM and VERIFIED separate rather than merging them into "known good".
`items.check_against_known()` validates a fresh ROM extraction against the
save-derived ids *only*; folding ROM-derived names into that set would make the
check compare the ROM against itself and quietly stop catching anything.

## Credits

Reverse engineering by inspecting real saves. Structure and approach owe a debt
to [Oh Mother](https://github.com/clickysteve/Oh-Mother-Earthbound-Save-File-Editor)
by clickysteve, which does the same job for vanilla EarthBound.

EarthBound Beginnings Remake is a fan project by Gabbls and contributors,
building on work begun by Clyde "Tomato" Mandelin. This tool ships no ROM,
patch, or game data.

MIT licensed — see [LICENSE](LICENSE).
