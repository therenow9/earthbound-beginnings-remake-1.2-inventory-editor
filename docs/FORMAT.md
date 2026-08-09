# EBBR SRAM format

Everything here was measured against real save files. Each entry is marked
**VERIFIED** (confirmed against two or more independent saves, or decoded into
values matching on-screen data) or **INFERRED** (single observation or reasoning
from context). Keep that distinction when adding to this file — conflating the
two is what produced every wrong conclusion during the original reverse
engineering.

## Container — VERIFIED

| property | vanilla EarthBound | EBBR |
|---|---|---|
| file size | 8 KB | 8 KB |
| block signature | `HAL Laboratory, inc.` (20 bytes) | same |
| block stride | `0x500` | `0x550` |
| data offset in block | `+0x18` | `+0x20` |
| data length | `0x4E0` | `0x530` |
| checksum 1 | `+0x14` | `+0x1C` |
| checksum 2 | `+0x16` | `+0x1E` |

- Checksum 1 = sum of all data bytes mod `0x10000`.
- Checksum 2 = XOR of the data as 16-bit little-endian words.
- Both stored little-endian. Confirmed: both matched exactly over
  `+0x20 .. +0x550` on four independent files.
- Six blocks: three save slots, each stored twice as mirror copies A and B.
- Locate blocks by scanning for the signature, never by assuming stride.

### Traps

**An all-zero block validates under every layout.** Sum and XOR of nothing are
both zero, and the stored checksum words are also zero. Empty blocks must be
excluded when auto-detecting layout or they will confirm any hypothesis.

**Signature spacing in a save-less image means nothing.** EarthBound's
anti-piracy routine probes for SRAM at startup by writing the signature at
`0x500` intervals. A blank SRAM therefore shows `0x500` spacing regardless of
which ROM produced it. This is a startup artifact, not structure. Do not infer
the game or the layout from it.

**Mirror copies A and B are not byte-identical** in real saves — their stored
checksums differ, so some field genuinely differs between them. Not yet
identified. Always write both copies and re-checksum both.

## Save data — offsets relative to the data section

| offset | field | status |
|---|---|---|
| `0x3C` | money, u32 LE | VERIFIED |
| `0x7A` | party roster, 1-based char ids, `00`-terminated | VERIFIED |
| `0x1D8` | character record table, 4 records, `0x5F` stride | VERIFIED |
| `0x513` | character name table, 7 bytes per entry | VERIFIED |

Character ids: `0` Ninten, `1` Ana, `2` Lloyd, `3` Teddy.
Text encoding: ASCII biased by `+0x30`.

## Character record — offsets relative to record start

| offset | field | status |
|---|---|---|
| `0x24` | inventory, 14 bytes, one item id per slot, `00` empty | VERIFIED |
| `0x32` | equip pointers, 4 bytes | VERIFIED |
| `0x36` | character id | VERIFIED |
| `0x46` | current HP, u16 LE | VERIFIED |
| `0x48` | max HP, u16 LE | INFERRED |
| `0x4C` | current PP, u16 LE | VERIFIED |
| `0x4E` | max PP, u16 LE | INFERRED |
| `0x5D` | `FF FF` record terminator | VERIFIED |

Equip pointers are **1-based indices into that character's own inventory**;
`00` means nothing equipped. Slot order is **weapon, pendant, band, coin**,
confirmed by decoding all four characters and matching the on-screen `E`
markers.

Bag position does not matter — the same item appears at different indices for
different characters and equips correctly from any of them.

Menu fill order is **row-major**: left column, right column, next row. Confirmed
by matching duplicate-item positions against screenshots in two saves. Note that
a 13-item bag leaves its gap at bottom-right under *either* ordering, so the gap
alone does not disambiguate.

## Unmapped

Level, EXP, base stats, PSI learned-flags, story/event flags, step counter, map
position, and whatever differs between mirror copies. Record regions around
`+0x06..0x09` and `+0x16..0x23` are high-entropy and unidentified.

## Method that works

Controlled diffing. Save in-game, make exactly one change, save again, diff the
two files. A single-item swap between adjacent bag slots produces two bytes
trading values — unmistakable. Broad "before and after two hours of play" diffs
produce hundreds of changed bytes and are useless.

When two saves from different points are all you have, use joint constraints
instead: items common to both bags must have equal ids at equal offsets, which
pins the array without needing a controlled change.
