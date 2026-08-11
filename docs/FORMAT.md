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
| `0x00` | player's own name, 12 bytes | VERIFIED |
| `0x0C` | second copy of the player name | VERIFIED |
| `0x24` | pet name in EarthBound; **unused by the remake** | VERIFIED |
| `0x2A` | favourite food, 12 bytes | VERIFIED |
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
| `0x06` | level, u8 | VERIFIED |
| `0x07` | experience, u24 LE | VERIFIED |
| `0x0B` | maximum HP, u16 LE | VERIFIED |
| `0x0D` | maximum PP, u16 LE | VERIFIED |
| `0x16` | Offense, u8 | VERIFIED |
| `0x17` | Defense, u8 | VERIFIED |
| `0x18` | Speed, u8 | VERIFIED |
| `0x19` | Fight, u8 | VERIFIED |
| `0x1A` | Wisdom, u8 | VERIFIED |
| `0x1B` | Strength, u8 | VERIFIED |
| `0x1C` | Force, u8 | VERIFIED |
| `0x46` | second copy of HP — **not** the maximum, purpose unknown | VERIFIED |
| `0x48` | current HP, u16 LE | VERIFIED |
| `0x4C` | second copy of PP — **not** the maximum, purpose unknown | VERIFIED |
| `0x4E` | current PP, u16 LE | VERIFIED |
| `0x5D` | `FF FF` record terminator | VERIFIED |

**These four were previously labelled the wrong way round.** `0x46`/`0x4C`
were read as the current values and `0x48`/`0x4E` guessed as the maxima. Every
real save has the party at full health, so all four hold the same number and
nothing distinguished them — the error was invisible and produced correct
output by coincidence.

Settled by writing values that differ and reading the game's own Status
screen. With `0x46 = 111` and `0x48 = 777` it printed:

    Hit Points:  777 / 542
    Psychic Points:  777 / 155

So `0x48` is *current* HP, and `0x4E` is current PP by the same test.

The maxima are at `0x0B` and `0x0D`, well away from the current values.
Confirmed the same way — writing 999 and 888 there produced
`Hit Points: 123 / 999` and `Psychic Points: 234 / 888`. They are also
distinguishable in the real saves without any emulator, but only via the one
character who is not at full health: in the pre-Teddy save Teddy's current HP
is `0` while `0x0B` already holds `345`.

Note the trap all of this is an instance of: a field pair that is equal in
every sample carries no information about which is which. Two saves agreeing
is not cross-validation when both are at full HP. The one row where they
differed — an inactive party member — was worth more than the other seven
combined.

### Level, experience and base stats — VERIFIED

Level is a plain byte at `0x06` and experience a u24 at `0x07`, which decodes
to exactly the 1050480 the Status screen reports. Note the width: experience
runs `0x07..0x09` and maximum HP begins at `0x0B`, so a u32 write would spill
into the gap and eventually into max HP.

The seven base stats are single bytes at `0x16..0x1C`, in the order Offense,
Defense, Speed, Fight, Wisdom, Strength, Force.

All of it was pinned in a single pass: write a distinct value to every byte of
`0x16..0x23` at once, then read the Status screen and see which number landed
where. `0x1D..0x23` produced no visible change and remain unidentified.

Confirmed together afterwards — level 61, experience 1234567, HP 700/750,
PP 250/300 and all seven stats written at once came back exactly on the Status
screen, with the game recomputing "Exp. for next level" from them.

Offense and Defense are stored rather than derived, but the game recalculates
both whenever equipment changes, so editing those two only lasts until the
player next changes gear.

### Stats are one byte each, and the game clamps — VERIFIED

All seven stats are `u8`, so 255 is a hard ceiling imposed by the format, not
a policy. Worth knowing that the *effective* value shares that byte with the
base, so base + equipment can exceed it: Ninten with base Offense 250 and
Hank's bat (+75) computes to 325. The game **clamps to 255 rather than
wrapping** — the Equip screen reads 255, not 69 — so a maxed stat is safe.

HP and PP are `u16` and could hold 65535; the editor caps them at 999 because
the game's readouts are three digits wide.

### Names and the favourite food — VERIFIED

Found by decoding every EB-text run in a save of each game and lining the two
up. The remake keeps these at **the same block-relative offsets as vanilla
EarthBound**, which is the strongest single piece of evidence that it inherited
EB's save structure wholesale rather than reimplementing it:

| offset | vanilla EarthBound | remake |
|---|---|---|
| `0x00` | `Alex` | `Jeremy` |
| `0x0C` | `Alex` again | `Jeremy` again |
| `0x24` | `King` — the dog | *all zeros* |
| `0x2A` | `Pizza` — favourite food | `Prime Rib` |
| `0x30` | `PSI Rockin ` — favourite thing | *tail of the food string* |

Three things the remake changed:

- **No pet name.** `0x24` is empty in every remake save, and the game never
  asks you to name a dog — confirmed by playing the opening. The field is
  inherited, not used. Do not expose it; editing it does nothing.
- **No favourite thing.** Mother 1 has no PSI-naming, so `0x30` is not a
  separate field.
- **A wider food field.** The remake writes long food names straight through
  what EarthBound treated as the boundary — a real save holds the 9-character
  `Prime Rib` running `0x2A..0x32`, which cannot fit EarthBound's 6-byte food
  field. Treated here as one 12-byte field, capped short of `MONEY` at `0x3C`
  so an over-long name can never reach it.

The player name is stored **twice**, at `0x00` and `0x0C`, the same duplication
the format uses for HP. Both must be written.

The game asks for the four character names and the food at the start, but the
player's own name only partway through — so a save from earlier legitimately
has `0x00` empty, and reading must cope with that.

Character renames are confirmed in-game: renaming all four through the editor
produced a save whose party box and Equip screen read the new names, with
equipment untouched.

### Party membership — VERIFIED

Three fields, all confirmed against the pair of real saves that bracket Teddy
joining, then re-confirmed by forcing him into the earlier save and loading it:

| where | absent | in the party |
|---|---|---|
| `0x7A` roster | id missing | 1-based id, in party order |
| record `+0x0F` | `01` | `00` |
| record `+0x38` | `FF FF` | `00 00` |

An unrecruited character also sits on 0 HP while their maximum is already
populated, so adding one by roster alone puts a corpse in the party — the
editor revives anyone on 0 HP as it adds them.

Adding works: Teddy loaded as a full fourth member, correct level and stats,
in a save from before he joins. Story flags are untouched, so his recruitment
scene presumably still fires later; that side of it is unexplored.

### Stat growth per level is not stored — INVESTIGATED, NOT FOUND

Worth recording so nobody repeats the search. The ROM holds no per-level stat
table, under either plausible layout:

- **Row-major** (seven stats contiguous per level): the exact byte sequences
  for all four characters at both observed levels — eight distinct 7-byte
  fingerprints — appear nowhere in the 4 MB image.
- **Column-major** (one level-indexed array per stat): anchoring on Offense
  matching at both levels gives 33 candidate bases; requiring the other six
  stats to match at both levels too — fourteen simultaneous constraints —
  eliminates every one, across ten different stride assumptions.

So the game computes growth in code, as the EarthBound engine does, from
per-character growth rates. Editing a level therefore cannot bring the stats
along with it without reproducing that routine.

Fitting a curve is not currently possible either: two saves give only two
level observations per character, and a two-parameter fit through two points
is exactly determined, so it would validate against nothing. The values are
also not a plain multiple of level — Lloyd's Offense equals his level at both
points and Ninten's is 1.68x at both, but Ana's drifts from 0.75x to 0.70x and
Lloyd's Force from 1.00x to 1.04x.

**What would settle it:** four to six saves per character at spread levels, or
a run of consecutive level-ups. Fit on part, predict the rest — that is the
line between deriving the growth and inventing it.

### Still unmapped

`0x00..0x05`, `0x0A`, `0x0F`, `0x10..0x15`, `0x1D..0x23`, `0x37..0x45` and
`0x4F..0x5C`. Known to be in there somewhere: the PSI learned-flags, the
melody counter the Status screen draws as `♪` symbols, and whatever differs
between mirror copies.

The editor writes both copies whenever HP or PP changes. `0x46`/`0x4C` have no
observed effect, but they match the current value in every genuine save, and
leaving one stale would create a pairing the game never produces.

Equip pointers are **1-based indices into that character's own inventory**;
`00` means nothing equipped. Slot order is **weapon, body, arms, other** —
the game's own names, read off its Equip screen.

Those slots were previously called *weapon, pendant, band, coin* here. The
order was right and the decoding was right; the names were invented from what
the four characters happened to be wearing. Slot 3 holds hats, ribbons and
galoshes as well as coins, which only makes sense once it is read as "Other".

Bag position does not matter — the same item appears at different indices for
different characters and equips correctly from any of them.

### Which items fit which slot — VERIFIED

Not in the save; in the ROM. Each item's 39-byte record carries a type byte at
record offset `0x19`, and the equippable ones occupy `0x10..0x1F`, four type
values per slot in the same order as the equip pointers:

| type | slot | examples |
|---|---|---|
| `0x10`, `0x11` | weapon | bats (27), guns (12) |
| `0x14` | body | charms and pendants (10) |
| `0x18` | arms | bracelets and bands (14) |
| `0x1C` | other | hats, ribbons, coins, galoshes (17) |

`0x20` and up is consumables and plot goods — 173 items that equip nowhere.

Established two ways. First, every one of the 9 distinct items observed
equipped across the two real saves falls in the slot the save actually has it
in; `tools/extract_items.py` re-checks this on every extraction and refuses to
write the table if it ever stops holding. Second, four items that were *never*
seen equipped — Plastic bat, Travel charm, Slap bracelet, Knit cap — were
written into the four slots this table predicts, and the game's Equip screen
showed each one exactly where predicted, with Offense and Defense recomputed.

This is what the editor uses to refuse nonsense like a hamburger in the weapon
slot. The game sorts its own Equip menu by this field and will never offer one,
so writing it would produce a save the game could not have made.

### Bags are contiguous, and the game compacts them — VERIFIED

There is never a hole. Items pack from slot 0; `00` only ever appears as
trailing padding. Sixteen real bags (four characters × two saves × both
mirrors) show no exceptions.

When an item leaves, everything after it **shifts down one** and the equip
pointers move to follow. Established from the two real saves without needing a
controlled experiment: Ninten's Onyx hook (index 6) is gone in the later save,
everything after it sits one slot earlier, and his weapon pointer moved
`12 -> 11` to keep pointing at Hank's bat.

This is why `add_item` inserts rather than overwriting and why `remove_item`
compacts: writing into an arbitrary slot would produce a bag shape the game
never creates.

There is **no item-count field**. If one existed it would have changed for
Ninten, Lloyd and Teddy (whose bag sizes changed between the two saves) but
not for Ana (whose did not), and no byte in the record behaves that way.

### Menu fill order is row-major — VERIFIED IN GAME

Left column, then right column, then next row. Previously inferred from
duplicate-item positions, which the notes correctly flagged as ambiguous.
Settled by injecting a known item into a known slot and photographing the
Goods menu: slot 13 rendered bottom-right, and slots 0 and 3 swapped places
on screen exactly as the byte swap predicted.

## Live inventory in WRAM — VERIFIED

Loading a save copies each character's bag into work RAM. Useful for
verification, not needed for editing:

| character | WRAM address |
|---|---|
| Ninten | `0x099F1` |
| Ana | `0x09A50` |
| Lloyd | `0x09AAF` |
| Teddy | `0x09B0E` |

Stride `0x5F` — the same as the SRAM character record stride. Addresses are
for BizHawk's `WRAM` domain and were located by searching for each bag's byte
signature; `tools/ingame_verify.py` re-finds them by signature rather than
trusting these, so they are documentation rather than load-bearing constants.

Equip pointers survive bag edits correctly: after a remove, an insert and a
swap, the on-screen `E` markers still sat on the intended items. That is the
strongest check available on the pointer-fixup logic.

The three pendants on sequential ids (`0x39`, `0x3A`, `0x3B`) turned out to be
**Rain**, **Flame** and **Earth** — elemental, not character-specific. That
removes the only reason to suspect pendants are character-restricted; the ids
were originally named after whoever happened to be wearing them.

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
