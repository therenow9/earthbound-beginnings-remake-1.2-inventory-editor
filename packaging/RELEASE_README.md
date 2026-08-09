# EBBR Save Editor

A simple save editor for **EarthBound Beginnings Remake**. It lets you change
your party's items, equipment and stats.

Normal EarthBound save editors don't work on the remake — it stores saves
differently, so they'll either refuse your file or wreck it. This one is built
for the remake specifically.

---

# ⚠️ READ THIS FIRST

**This is experimental software. It can and will break saves.**

Not "might, in theory". Editing a save file means writing bytes into a game
that was never designed to be edited, and there are things in there nobody has
figured out yet. Sooner or later something will go wrong for somebody.

**So: back up your save before you touch it.**

Copy your `.srm` somewhere safe — your desktop, a folder called `backup`,
anywhere. Do it every time. The editor also makes its own backup file next to
your save each time it saves, but do not rely on that alone.

If your save is precious and irreplaceable, honestly, think twice before
using this on it.

### Only tested on remake v1.2

That's the version this was built and tested against. Other versions may work
fine, or may not — nobody has tried. The item list was read out of a v1.2 ROM,
so on a different version the item *names* could be wrong even if the editing
works, which would be a confusing way to lose a save. If you're on something
else, be extra careful and definitely keep that backup.

### Some of this is riskier than the rest

Not everything here is equally tested, and it's worth knowing which parts are
which.

**Items and equipment — mostly safe.** This is where the tool started and
where nearly all the testing went. Edits have been checked against the running
game repeatedly.

**Removing party members, and pushing levels or stats to extremes — very
untested.** Take out someone the story expects to be there and you could get
stuck in a scene that never finishes. Set a level of 99 with level-20 stats
and you've made something the game would never create on its own; nobody knows
how it behaves at the edges.

If you want to play with those, do it on a copy of your save, not on a
playthrough you'd be upset to lose.

---

## What it can do

- Add, remove and reorder **items** in each character's bag
- Change **equipment** — weapon, body, arms, other
- Change **HP and PP**, current and maximum
- Change **level, EXP and stats**
- Change **money**
- Add, remove and **reorder party members**
- Works on any of your three save slots

## What it can't do

This is a small tool. It edits inventory and stats and that's about it. It is
**not** a full-featured editor like [Oh Mother](https://github.com/clickysteve/Oh-Mother-Earthbound-Save-File-Editor)
(which is for the original EarthBound, not the remake).

Things it does **not** touch:

- **Story progress and event flags.** You cannot skip ahead, unlock areas, mark
  a boss as beaten, or fix a broken playthrough. None of that is editable.
- **PSI abilities.** You can't teach or remove them.
- **Melodies.**
- **Where you are on the map.**

Some other limits worth knowing:

- **Stats max out at 255.** That's a limit of the save format, not a choice.
- **HP and PP max out at 999** in this editor.
- **Changing level does not change stats.** The game calculates stat growth
  internally in a way we can't reproduce, so if you bump someone to level 60
  you'll need to set their stats yourself.
- **Offense and Defense don't stick.** The game recalculates those two whenever
  a character changes equipment, so your edit gets overwritten. The other five
  stats stay.
- **Adding a party member early is untested territory.** The story doesn't know
  they've joined, so scenes may behave strangely. Removing someone the story
  needs could leave you stuck.

---

## How to use it

**1. Close your emulator completely.**

Really. Your emulator writes the save file when it closes, so if it's open it
will overwrite whatever you change. This is the number one reason people think
the editor "didn't work".

**2. Find your save file.**

It's a `.srm` file named after your ROM. If your ROM is `EBBR.sfc`, your save
is `EBBR.srm`, usually sitting right next to it or in your emulator's saves
folder.

**3. Back it up.** Copy it somewhere safe. Yes, again. 🙂

**4. Run `EBBR-Save-Editor.exe`,** then **File → Open** and pick your save.

Windows may say the publisher is unknown, because the file isn't signed by a
company. Click **More info → Run anyway**.

**5. Make your changes, then File → Save.**

**6. Open your emulator and check it worked** before you play for an hour.

You don't need the ROM, Python, or anything else installed for this — just the
.exe and your save file.

---

## Getting around

Pick a character with the tabs along the top. Their bag is on the left, their
equipment on the right.

**Add an item** — click **Add…** and start typing. Type "pendant" to see all
the pendants, and so on. If you want it in a specific spot in the bag, click
that spot first.

**Remove an item** — click it, then **Remove**.

**Move an item** — click it and use the **▲ ▼** buttons.

**Equip something** — use the dropdowns on the right. They only show things
that character is carrying and can actually wear, so if one looks empty, give
them a suitable item first. Food won't appear in the weapon slot.

**Party members** — each character has an "In the party" tick box, and the
**◀ ▶** buttons beside it move them earlier or later in the party order.
The position is shown next to them ("position 2 of 4").

**HP and PP** have two boxes each: current, then maximum. Current can't go above
maximum, so raise the maximum first if you want a big number.

---

## If something goes wrong

**"… is a EarthBound (USA) save, not the remake."**
That's a save from the original EarthBound. This editor only works on the
remake, and editing a vanilla save would break it, so it stops.

**"This SRAM contains no saves."**
The file is empty. This usually means your emulator couldn't match the save to
your ROM and reset it. Check that your ROM and `.srm` have the same name and
live in the same folder, away from any other EarthBound files.

**My change didn't show up in the game.**
Your emulator was probably still open. Close it fully, then edit the save.

**Something is genuinely broken.**
Restore your backup. This is why you made one.

---

## Reporting a bug

[Open an issue here.](https://github.com/therenow9/earthbound-beginnings-remake-1.2-inventory-editor/issues)

Please check the problems above first — those are the most common reports and
none of them is really a bug.

It helps a lot if you include:

- **What you did**, step by step
- **What happened**, and what you expected instead
- **Which version** of the editor (Help → About) and of the remake

### Save files help more than anything else

If you don't mind sharing them, **send the save from before the problem and
the save from after** — both files, not just one.

A single save shows the end state. A pair shows exactly which bytes changed,
which is usually the whole answer in about a minute. This is genuinely the
difference between a bug that gets fixed and one that gets guessed at.

**The good news is you probably already have the "before" file.** Every time
the editor saves, it writes a backup next to your save with `.bak` on the end —
`EBBR.srm.bak`, or `.bak1`, `.bak2` and so on if there are several. That
backup is your save as it was *before* that edit. So:

- **before** → the `.bak` file (or your own backup copy)
- **after** → the `.srm` itself

Attach both. If the problem showed up in the game rather than in the editor,
the most useful "after" is a save made *in game* once things had gone wrong.

Copy in the exact error message if you saw one.

**Please don't attach a ROM or patch file.** This project contains no game data
and can't accept any. Your save file on its own is fine.

Two things that aren't bugs, as above: Offense and Defense showing different
numbers in the editor and the game, and stats not changing when you change
level.

---

Source code, a command-line version, and technical notes:
<https://github.com/therenow9/earthbound-beginnings-remake-1.2-inventory-editor>

Contains no ROM, patch, or game data. MIT licensed.

## Future plans

Honestly, not many. This does what it was built to do, and it's staying
roughly as it is.

**Not planned:**

- Story flag or event editing — you will not be able to skip ahead, unlock
  areas, or repair a stuck playthrough with this, now or later
- PSI, melodies, map position
- Level editing that also works out your stats for you

Those first ones aren't understood well enough to touch safely, and the last
would mean recreating the game's internal stat maths, which isn't stored
anywhere in the ROM to copy from.

**Minor bugs will get looked at.** Beyond that, please treat this as finished
rather than something actively being developed. Feature requests probably
won't go anywhere, and that's not rudeness — it's just the honest answer.

## Not affiliated with the EBBR team

**This save editor was made entirely by me (therenow9), on my own, as an
unofficial third-party tool.**

**Gabbls, livvy94, and everyone else who worked on EarthBound Beginnings
Remake had nothing to do with it.** They did not build it, review it, endorse
it, or ask for it. It is not part of the remake and is not supported by them.

So please:

- **Don't report problems with this editor to them.** Bugs belong in the issue
  tracker linked above, not with the remake's developers.
- **Don't blame them if it breaks your save.** That would be on me, and on
  the fact that you were warned it might.
- Don't treat anything here as official information about the remake.

### A genuine thank you

None of the above is a complaint — the opposite, really.

EarthBound Beginnings Remake is an incredible piece of work. Rebuilding Mother
1 inside EarthBound's engine is an enormous undertaking, and the care that has
gone into it shows everywhere. Huge thanks to Gabbls, livvy94 and everyone else
who has put time into the project, and to Clyde "Tomato" Mandelin, whose work
it builds on.

I only made this editor because I enjoyed the remake enough to want to poke
around inside it. It exists because of their work, and I really do appreciate
all of it.

Thanks also to
[Oh Mother](https://github.com/clickysteve/Oh-Mother-Earthbound-Save-File-Editor)
by clickysteve, which does a much bigger job for the original EarthBound and
was the model for how to approach this.
