# EBBR Save Editor

Edit party inventories in **EarthBound Beginnings Remake** — the SNES ROM hack
that rebuilds Mother 1 inside EarthBound's engine.

Existing EarthBound save editors do not work on it. The remake changed the SRAM
block geometry and reassigned the item table, so a vanilla editor will either
refuse your file or corrupt it.

> ⚠️ **Keep a backup.** The editor writes a `.bak` next to your save every time
> it saves, but a bad edit can still cost you a file.

---

## What you need

Just the `.exe` and your save file. **No ROM, no patch, no Python, nothing to
install** — the editor never opens a ROM, and every item name is already built
into the executable.

(A ROM is only needed by developers regenerating the item table from source.
This project ships no game data and never asks you for any.)

## Getting started

1. Download **`EBBR-Save-Editor.exe`** below and run it.
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
| **Equipment** | weapon, body, arms and other, per character |
| **HP / PP** | current and maximum |
| **Level & EXP** | per character |
| **Stats** | Offense, Defense, Speed, Fight, Wisdom, Strength, Force |
| **Money** | on hand |

Still not editable: PSI, the melody counter, and story flags. Those are not
mapped, and guessing at them is how save editors corrupt files.

One caveat on **Offense and Defense**: the game recalculates both whenever the
character changes equipment, so edits to those two last only until then. The
other five stats stick.

### It will stop you doing impossible things

**Items only go in slots they belong in.** Each equipment dropdown lists only
what that character is carrying *that actually fits* — a hamburger is never
offered as a weapon, and a pendant is never offered as arms. The categories
come from the ROM's own item data, the same field the game sorts its Equip
menu by, so the editor agrees with the game by construction.

**Current HP and PP cannot exceed their maximum.** Type a bigger number and it
snaps to the cap. To go higher, raise the maximum first — that field is
editable too, and both are capped at 999, which is as wide as the game's
displays go.

## Using it

**Add an item** — select the bag slot you want it to land in and click `Add…`,
then start typing. The search matches names and hex ids, so `pendant` and `39`
both work. With nothing selected it appends to the end.

**Remove** takes the item out and closes the gap, exactly as the game does when
you use something up. Anything equipped from that slot becomes unequipped, and
everything below shifts up with its equipment still attached.

**▲ / ▼** reorder. Equipment follows the item, not the slot number.

**Equipment dropdowns** only list what that character is carrying *and* can
wear in that slot, because the game stores equipment as a pointer into their
own bag. Give them the item first, then equip it. An empty dropdown means they
have nothing suitable.

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

## Reporting a bug

Open an issue:
<https://github.com/therenow9/earthbound-beginnings-remake-1.2-inventory-editor/issues>

Check the three cases above first — they account for most reports and none of
them is a bug in the editor.

What to include:

1. **What you did**, specifically enough to repeat. "Gave Ana a Silver sword
   and equipped it" beats "equipment is broken".
2. **What happened, and what you expected instead.** If a number is wrong, say
   what the editor showed *and* what the game showed — those disagreeing is
   itself the useful signal.
3. **Your `.srm`**, if you are comfortable sharing it. This matters more than
   everything else combined: nearly every problem is reproducible in seconds
   with the actual file and guesswork without it. It is a save file, not
   personal data, and it is useless without the ROM.
4. **Versions** — the editor version from Help ▸ About, your EBBR version
   (1.2, or whatever the title screen says), and which emulator.

If the editor showed an error message, paste it verbatim.

**Please do not attach a ROM or a patch**, to an issue or anywhere else. This
project ships no game data and cannot accept any. A save file on its own is
fine.

### Something to check before reporting a wrong number

Stats have two places they can disagree. **Offense and Defense** are
recalculated by the game whenever a character changes equipment, so the editor
showing one value and the game another is expected for those two. The same goes
for maximum HP and PP after a level-up. Everything else should match exactly —
if it does not, that is worth an issue.

---

Source, the command-line version, and the format notes:
<https://github.com/therenow9/earthbound-beginnings-remake-1.2-inventory-editor>

Ships no ROM, patch, or game data. MIT licensed.

EarthBound Beginnings Remake is a fan project by Gabbls and contributors,
building on work begun by Clyde "Tomato" Mandelin. Structure and approach owe a
debt to [Oh Mother](https://github.com/clickysteve/Oh-Mother-Earthbound-Save-File-Editor)
by clickysteve, which does the same job for vanilla EarthBound.
