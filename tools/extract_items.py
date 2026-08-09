"""Read the item name table out of a ROM into data/items.json.

CoilSnake is not needed for this. The item table is a flat array of fixed-size
records with the name at the start of each one, stored in ordinary EB text
(ASCII biased by +0x30), so it can be read directly.

How the geometry was established, in case it has to be redone for another
build: search the ROM for a few known names encoded with the +0x30 bias, then
divide the gap between two hits by the gap between their ids. Every pair gave
39, and back-solving the base from any hit gave exactly 0x155000.

    ATM card   id 0xB1  @ 0x156AF7
    Town map   id 0xCA  @ 0x156EC6   (0x3CF gap / 25 ids = 39)

The extraction is only trusted if it reproduces the names already established
independently from real saves -- see items.check_against_known(). A mismatch
means the base or stride is wrong and the whole table is garbage, so this exits
non-zero and writes nothing rather than emitting a plausible-looking table.

Usage:
    python tools/extract_items.py <rom> [-o data/items.json]
                                        [--compare <vanilla rom>]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ebbr import items, layout as L      # noqa: E402

#: Verified against EarthBound Beginnings Remake 1.2 (USA) and, as it happens,
#: stock EarthBound (USA) -- both games keep the table at the same address.
ITEM_TABLE_BASE = 0x155000
ITEM_ENTRY_SIZE = 39
ITEM_COUNT = 256

#: The record continues past the name with stats and flags. Names terminate on
#: a 0x00, but cap the read so a missing terminator cannot spill binary into a
#: name. The longest real name is well under this.
NAME_MAX = 24


def read_table(rom: bytes, base: int = ITEM_TABLE_BASE,
               stride: int = ITEM_ENTRY_SIZE,
               count: int = ITEM_COUNT) -> dict[int, str]:
    """Decode {id: name}, skipping blank and non-text entries."""
    out: dict[int, str] = {}
    for item_id in range(count):
        # Id 0 is the empty-bag-slot marker in save data, not an item. The ROM
        # does hold a record there (named "Null"), but importing it would let
        # `give` resolve a name to "nothing".
        if item_id == 0:
            continue
        start = base + item_id * stride
        raw = rom[start:start + NAME_MAX]
        if len(raw) < NAME_MAX:
            break
        name = L.decode_text(raw)
        # decode_text renders undecodable bytes as '?', which is how a wrong
        # base or stride shows up. Treat those entries as absent.
        if not name.strip() or "?" in name:
            continue
        out[item_id] = name
    return out


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("rom", help="the patched remake ROM")
    p.add_argument("-o", "--out", default=str(items.DEFAULT_TABLE))
    p.add_argument("--compare", metavar="ROM",
                   help="second ROM (e.g. vanilla EarthBound) to diff against")
    p.add_argument("--base", type=lambda s: int(s, 0), default=ITEM_TABLE_BASE)
    p.add_argument("--stride", type=lambda s: int(s, 0), default=ITEM_ENTRY_SIZE)
    p.add_argument("--count", type=lambda s: int(s, 0), default=ITEM_COUNT)
    args = p.parse_args(argv)

    rom = Path(args.rom).read_bytes()
    table = read_table(rom, args.base, args.stride, args.count)
    print(f"{Path(args.rom).name}: {len(table)} named entries "
          f"of {args.count} at 0x{args.base:06X} stride {args.stride}")

    problems = items.check_against_known(table)
    if problems:
        print("\nREFUSING TO WRITE — extraction disagrees with known ids:",
              file=sys.stderr)
        for line in problems:
            print(f"  {line}", file=sys.stderr)
        print("\nThe base or stride is wrong. Nothing was written.",
              file=sys.stderr)
        return 1

    checked = sum(1 for _, (_, prov) in items.ITEMS.items()
                  if prov == items.VERIFIED)
    print(f"cross-check: all {checked} save-verified ids match")

    if args.compare:
        other = read_table(Path(args.compare).read_bytes(),
                           args.base, args.stride, args.count)
        ids = sorted(set(table) | set(other))
        diff = [i for i in ids if table.get(i) != other.get(i)]
        print(f"vs {Path(args.compare).name}: {len(ids) - len(diff)} identical, "
              f"{len(diff)} reassigned")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps({f"0x{i:02X}": n for i, n in sorted(table.items())},
                   indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8")
    print(f"wrote {out} ({len(table)} entries)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
