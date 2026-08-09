# EBBR SRAM format

Everything here was measured against real save files or read out of the ROM.
Each entry is marked **VERIFIED** (confirmed against two or more independent
saves, or decoded into values matching on-screen data), **ROM** (read from the
ROM itself), or **INFERRED** (single observation or reasoning from context).
Keep those distinctions when adding to this file — conflating them is what
produced every wrong conclusion during the original reverse engineering.

Note that "two independent saves" means two *different* saves. A renamed copy
of one is not corroboration, and one of the files supplied to this project
turned out to be exactly that.

## Container — VERIFIED

| property | vanilla EarthBound | EBBR |
|---|---|---|
| file size | 8 KB | 8 KB |
| block signature | `HAL Laboratory, inc.` (20 bytes) | same |
| block stride | `0x500` | `0x550` |
| data offset in block | `+0x20` | `+0x20` |
| data length | `0x4E0` | `0x530` |
| checksum 1 | `+0x1C` | `+0x1C` |
| checksum 2 | `+0x1E` | `+0x1E` |

**The header layout is identical between the two games.** Only the block
geometry differs. An earlier revision of this table gave vanilla as data
`+0x18` with checksums at `+0x14`/`+0x16`; that was wrong, and it survived
because no test or fixture ever exercised the vanilla layout — the real vanilla
save simply failed to load at all. Corrected by brute-forcing the geometry
against a real stock EarthBound save.

- Checksum 1 = sum of all data bytes mod `0x10000`.
- Checksum 2 = XOR of the data as 16-bit little-endian words.
- Both stored little-endian. Confirmed: both matched exactly over
  `+0x20 .. +0x550` on four independent EBBR files, and over
  `+0x20 .. +0x500` on both mirror copies of a real vanilla save
  (sums `C57F`/`E205` and `C583`/`E201`).
- `data_offset + data_len == block_stride` for both layouts. The data fills the
  block exactly; a geometry where it does not is wrong by construction.
- Six blocks: three save slots, each stored twice as mirror copies A and B.
- Locate blocks by scanning for the signature, never by assuming stride.

Because both games checksum from the same base offset, **stride is the only
discriminator between them**. Detection works by seeing which layout validates
more non-empty blocks; neither validates the other's file, since the spans
covered differ.

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

Money, roster, and both tables were re-confirmed against two real remake saves
(mid-game and post-Teddy): money decoded to `$18`, matching the in-game display
on both, and the roster shortened from three names to four in the expected order.

Character ids: `0` Ninten, `1` Ana, `2` Lloyd, `3` Teddy.
Text encoding: ASCII biased by `+0x30`.

## Item table — in the ROM, not the save

Item ids in a save index a table stored in the ROM itself:

| property | value | status |
|---|---|---|
| base (file offset) | `0x155000` | VERIFIED |
| entry size | 39 bytes | VERIFIED |
| name | at entry start, `00`-terminated, EB text | VERIFIED |
| entry count | 256 (253 usable in the remake; id 0 is the empty marker) | VERIFIED |

Established by searching the ROM for known names encoded with the `+0x30` bias
and dividing the gap between hits by the gap between their ids — every pair gave
39, and back-solving the base from any hit gave exactly `0x155000`. All 14
save-verified ids decode to their known names.

**Stock EarthBound keeps its table at the same base and stride**, so the remake
did not move the table, only rewrote it: 128 of 253 entries differ. That diff
is a free correctness check and `tools/extract_items.py --compare` emits it.

The rest of each 39-byte record (stats, equip flags, price) is unmapped; only
the name is read.

**Trap:** a base off by one whole record still decodes to 253 real item names —
just the wrong ones. Nothing internal to the extraction can detect this, which
is why `items.check_against_known()` gates it against ids established
independently from saves.

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

`0x48` and `0x4E` stay INFERRED. In every real save examined so far the party
is at full health, so current and max are equal and the pair is indistinguishable.
Consistent with the guess, but no evidence for it. A save taken after damage and
before healing would settle it in one look.

Equip pointers are **1-based indices into that character's own inventory**;
`00` means nothing equipped. Slot order is **weapon, pendant, band, coin**,
confirmed by decoding all four characters and matching the on-screen `E`
markers.

Bag position does not matter — the same item appears at different indices for
different characters and equips correctly from any of them.

The three pendants on sequential ids (`0x39`, `0x3A`, `0x3B`) turned out to be
**Rain**, **Flame** and **Earth** — elemental, not character-specific. That
removes the only reason to suspect pendants are character-restricted; the ids
were originally named after whoever happened to be wearing them.

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
