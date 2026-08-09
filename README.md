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

**Scope: inventory and equipment.** Not levels, stats, PSI, story flags or map
warps — those need open-ended reverse engineering for little benefit. Items are
the useful part and the part that is already understood.

Working: container handling (block detection, checksum validation and repair,
mirror-copy consistency), character records, inventories, equipment, and a CLI.

The item table is complete: all 253 named ids, read straight out of the ROM by
[tools/extract_items.py](tools/extract_items.py). You supply your own ROM; the
repo ships names and ids only.

**Not yet proven: writing.** Every read path is confirmed against real saves,
but no edit has been round-tripped through the actual game yet. Treat `give`
and `equip` as experimental until it has. See [docs/PLAN.md](docs/PLAN.md).

## Install

```bash
git clone <your-repo-url>
cd ebbr-save-editor
pip install -e ".[dev]"
```

Python 3.10+. No required runtime dependencies.

## Use

```bash
ebbr info save.srm                          # summarise slots, party, bags
ebbr items                                  # list known item ids
ebbr items pendant                          # search
ebbr give save.srm Ninten "Goddess band"    # first free bag slot
ebbr give save.srm Teddy 0xE6 --slot 3      # by id, specific slot
ebbr equip save.srm Teddy weapon 0          # point weapon at bag slot 0
ebbr diff a.srm 0 0 --file-b b.srm          # field-named byte diff
```

`diff` translates offsets into field names where they are known, which is what
makes mapping new fields tractable.

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
