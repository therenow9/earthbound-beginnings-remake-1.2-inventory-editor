# EBBR Save Editor

Edit party inventories in **EarthBound Beginnings Remake** — the SNES ROM hack
that rebuilds Mother 1 inside EarthBound's engine.

Existing EarthBound save editors do not work on it. The remake changed the SRAM
block geometry and reassigned the item table, so a vanilla editor will either
refuse your file or corrupt it.

> ⚠️ **Keep a backup.** The editor writes a `.bak` next to your save every time
> it saves, but a bad edit can still cost you a file.

---

## Getting started

1. Download **`EBBR-Save-Editor.exe`** below and run it. There is nothing to
   install — no Python, no dependencies.
2. `File → Open`, and pick your `.srm`.
3. Edit. `File → Save`.

Windows may warn that the publisher is unknown, because the executable is not
code-signed. *More info → Run anyway*, or build it yourself from source.

## Finding your save

Emulators name the save after the ROM. If your ROM is `EBBR.sfc`, look for
`EBBR.srm` beside it, or in your emulator's saves folder.

**Filenames are load-bearing.** bsnes matches SRAM to ROM purely by filename and
silently reinitialises the file when they do not match — which looks exactly
like "my edit didn't work". Keep the remake ROM in its own folder, away from
vanilla EarthBound, and **close the emulator fully before editing**, since SRAM
is written out on exit and will overwrite your changes.

## What you can edit

| | |
|---|---|
| **Save slot** | any of the three, if it has a save in it |
| **Items** | add, remove and reorder each character's 14-slot bag |
| **Equipment** | weapon, pendant, band and coin, per character |
| **HP / PP** | current values |
| **Money** | on hand |

Deliberately not editable: levels, EXP, base stats, PSI and story flags. Those
would need open-ended reverse engineering for little benefit, and guessing at
them is how save editors corrupt files.

Maximum HP and PP are not shown, because they are not stored in the save — the
game derives them. Setting current HP above the maximum works and displays,
but the game may clamp it back after a battle.

## Using it

**Add an item** — select the bag slot you want it to land in and click `Add…`,
then start typing. The search matches names and hex ids, so `pendant` and `39`
both work. With nothing selected it appends to the end.

**Remove** takes the item out and closes the gap, exactly as the game does when
you use something up. Anything equipped from that slot becomes unequipped, and
everything below shifts up with its equipment still attached.

**▲ / ▼** reorder. Equipment follows the item, not the slot number.

**Equipment dropdowns** only list what that character is carrying, because the
game stores equipment as a pointer into their own bag. Give them the item
first, then equip it.

## Is this safe?

Every edit is checked against the real game, not just against itself. Saves
written by this editor are loaded in an emulator and the game's live inventory
is read back out of its RAM and compared byte for byte against what was
written; the on-screen Goods menu is checked too, including which items still
show the `E` equipped marker.

The editor also keeps the two mirror copies every save slot contains in step
and recomputes both checksums, which is what makes the game accept the file at
all.

That said — it is a save editor for a fan ROM hack. Keep the `.bak`.

## Troubleshooting

**"… is a EarthBound (USA) save, not the remake."**
That is a vanilla EarthBound save. This tool only handles the remake; editing a
vanilla save with remake geometry would corrupt it, so it refuses.

**"This SRAM contains no saves."**
The file is blank. Almost always a ROM/filename mismatch in the emulator rather
than a damaged save — see *Finding your save* above.

**My edit did not show up in game.**
The emulator was probably still running and overwrote the file on exit. Close
it completely, then edit.

---

Source, the command-line version, and the format notes:
<https://github.com/therenow9/earthbound-beginnings-remake-1.2-inventory-editor>

Ships no ROM, patch, or game data. MIT licensed.

EarthBound Beginnings Remake is a fan project by Gabbls and contributors,
building on work begun by Clyde "Tomato" Mandelin. Structure and approach owe a
debt to [Oh Mother](https://github.com/clickysteve/Oh-Mother-Earthbound-Save-File-Editor)
by clickysteve, which does the same job for vanilla EarthBound.
