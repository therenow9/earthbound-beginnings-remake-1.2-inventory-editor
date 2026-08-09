# EBBR Save Editor

Edit your party's items, equipment and stats in **EarthBound Beginnings
Remake**.

Normal EarthBound save editors don't work on the remake — it stores saves
differently, so they'll either refuse your file or break it. This one is built
for the remake.

> ⚠️ **Keep a backup.** The editor makes one for you every time it saves, but
> a bad edit can still cost you a file.

---

## Getting started

1. Download **`EBBR-Save-Editor.exe`** below and run it.
2. **File → Open**, and pick your save file.
3. Make your changes, then **File → Save**.

That's it. You don't need the ROM, Python, or anything else installed — just
the .exe and your save.

Windows may say the publisher is unknown, because the file isn't
code-signed. Click **More info → Run anyway**.

## Finding your save file

Your save is a **`.srm`** file, named after your ROM. If your ROM is
`EBBR.sfc`, look for `EBBR.srm` next to it, or in your emulator's saves folder.

**Close your emulator before editing.** It writes the save file when it closes,
which will wipe out your changes. This is the number one reason edits seem to
"not work".

## What you can change

| | |
|---|---|
| **Items** | add, remove and reorder each character's bag |
| **Equipment** | weapon, body, arms and other |
| **HP and PP** | current and maximum |
| **Level and EXP** | |
| **Stats** | Offense, Defense, Speed, Fight, Wisdom, Strength, Force |
| **Money** | |

You can pick any of the three save slots at the top.

PSI, melodies and story progress can't be changed. We haven't figured out where
the game keeps those, and guessing is how save editors corrupt files.

## How to use it

**Adding an item** — click **Add…** and start typing. Searching works on
names, so type "pendant" to see all of them. Pick one and it goes into the bag.

If you want it in a particular spot, click that spot in the bag first.

**Removing** — click the item, then **Remove**.

**Reordering** — click an item and use the **▲ ▼** buttons.

**Equipping** — use the dropdowns on the right. They only show things that
character is carrying and can actually wear, so if a dropdown looks empty, give
them a suitable item first.

## Good to know

**You can't equip the wrong kind of thing.** Food won't show up in the weapon
slot. The editor uses the game's own item categories, so it agrees with the
game.

**HP and PP can't go above the maximum.** Type a bigger number and it drops
back to the cap. Want more? Raise the maximum first — it's the second box. Both
max out at 999.

**Offense and Defense don't always stick.** The game recalculates those two
whenever a character changes equipment, so your edit will be replaced next time
they swap gear. The other five stats stay put.

**Changing level doesn't change stats.** The game works those out internally
and we can't reproduce it, so set the stats yourself if you want them to match.

## If something goes wrong

**"… is a EarthBound (USA) save, not the remake."**
That's a save from the original EarthBound. This editor only works on the
remake — editing a vanilla save would break it, so it stops.

**"This SRAM contains no saves."**
The file is empty. Usually this means the emulator didn't match your save to
your ROM, and reset it. Check that your ROM and `.srm` have the same name and
sit in the same folder, away from any other EarthBound files.

**My change didn't show up in the game.**
The emulator was probably still open. Close it fully, then edit the save.

## Found a bug?

[Open an issue here.](https://github.com/therenow9/earthbound-beginnings-remake-1.2-inventory-editor/issues)

Please check the three problems above first — those are the most common
reports, and none of them is actually a bug.

It helps a lot if you include:

- **What you did**, step by step
- **What happened**, and what you expected instead
- **Your `.srm` file**, if you don't mind sharing — this is by far the most
  useful thing, since it usually makes the problem easy to reproduce
- **Which version** of the editor (Help → About) and of the remake you're using

Copy in the exact error message if you saw one.

**Please don't attach a ROM or patch file.** This project doesn't include any
game data and can't accept any. Your save file on its own is fine.

One thing that isn't a bug: Offense and Defense showing different numbers in
the editor and the game, as explained above. Same for maximum HP and PP after
levelling up. Anything else that doesn't match is worth telling us about.

---

Source code, a command-line version, and technical notes:
<https://github.com/therenow9/earthbound-beginnings-remake-1.2-inventory-editor>

Contains no ROM, patch, or game data. MIT licensed.

EarthBound Beginnings Remake is a fan project by Gabbls and contributors,
building on work begun by Clyde "Tomato" Mandelin. Thanks to
[Oh Mother](https://github.com/clickysteve/Oh-Mother-Earthbound-Save-File-Editor)
by clickysteve, which does the same job for the original EarthBound.
