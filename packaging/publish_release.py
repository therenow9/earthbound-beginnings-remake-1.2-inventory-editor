"""Cut a GitHub release: tag, notes, and the built .exe.

    gh auth login                        # once, interactive
    python packaging/publish_release.py

Builds the executable if it is missing, tags the current commit, and publishes
a release with EBBR-Save-Editor.exe and the user-facing README attached.

Re-runnable: pass --force to move an existing tag and replace the release.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXE = ROOT / "dist" / "EBBR-Save-Editor.exe"
READ_ME = ROOT / "packaging" / "RELEASE_README.md"


def gh() -> str:
    found = shutil.which("gh") or shutil.which(
        "gh", path=r"C:\Program Files\GitHub CLI")
    if not found:
        sys.exit("GitHub CLI not found. Install it, then `gh auth login`.")
    return found


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    print("$", " ".join(str(c) for c in cmd))
    return subprocess.run([str(c) for c in cmd], cwd=ROOT, **kw)


def version() -> str:
    """Read the single source of truth in src/ebbr/__init__.py.

    Parsed rather than imported so this keeps working without the package
    installed.
    """
    text = (ROOT / "src" / "ebbr" / "__init__.py").read_text(encoding="utf-8")
    m = re.search(r'^__version__\s*=\s*"([^"]+)"', text, re.M)
    if not m:
        sys.exit("no __version__ in src/ebbr/__init__.py")
    return m.group(1)


NOTES = """\
A simple save editor for **EarthBound Beginnings Remake** — items, equipment
and stats.

## ⚠️ This is experimental. It can and will break saves.

**Back up your `.srm` before you use this.** Every time. The editor writes its
own backup too, but do not rely on that alone. If your save is precious and
irreplaceable, think twice.

Also: **close your emulator before editing.** It writes the save file when it
closes and will overwrite your changes. This is the single most common reason
people think the editor did nothing.

**Tested against EarthBound Beginnings Remake v1.2 only.** Other versions may
work or may not — nobody has tried. The item list was read out of a v1.2 ROM,
so if another version moved items around, the names shown could be wrong even
though the editing itself works.

## What it does

- Add, remove and reorder items in each character's bag
- Change equipment: weapon, body, arms, other
- Change HP and PP, current and maximum
- Change level, EXP and the seven stats
- Change money
- Add or remove party members
- Any of your three save slots

## What it does not do

This is a small tool for inventory and stats. It is **not** a full-featured
editor like Oh Mother, which does a much bigger job for the original
EarthBound.

It cannot touch **story progress or event flags** — you cannot skip ahead,
unlock areas, mark a boss beaten, or repair a broken playthrough. PSI,
melodies and map position are also off limits. Nobody has worked out where the
game keeps those, and guessing is how save editors corrupt files.

Other limits: stats cap at 255 (a limit of the save format, not a choice),
changing level does not recalculate stats, and Offense/Defense are overwritten
by the game whenever a character changes equipment.

## Some of this is riskier than the rest

**Items and equipment** have had the most testing and appear to be mostly
safe. That is where the tool started and where most of the work went.

**Removing party members, and pushing levels or stats to extremes, are very
lightly tested.** Removing someone the story expects to be present could leave
you stuck in a scene that never ends. An implausible level with mismatched
stats is a state the game would never produce on its own, and nobody knows
what it does at the edges.

If you are going to experiment with those, do it on a copy, not on a
playthrough you care about.

## Getting it running

Download **EBBR-Save-Editor.exe** below. Nothing to install and **no ROM
needed** — it only ever opens your `.srm`, and all 253 item names are built in.

Windows will warn about an unknown publisher because the file is not
code-signed. More info → Run anyway.

**Read RELEASE_README.md** below for the full guide: finding your save file,
what each control does, and what to do when something goes wrong.

Vanilla EarthBound saves are refused on purpose — the remake stores saves
differently, and writing remake data into a vanilla save would wreck it.

## Future plans

Not many — this does what it was built to do and is staying roughly as it is.

**Not planned:** story flag or event editing, PSI, melodies, map position, or
level editing that recalculates your stats. The first group is not understood
well enough to touch safely; the last would mean recreating the game's stat
growth maths, which is not stored anywhere in the ROM to copy from.

Minor bugs will get looked at. Beyond that, please treat this as finished
rather than actively developed.

## Not affiliated with the EBBR team

**This editor was made entirely by me (therenow9), on my own. It is an
unofficial third-party tool.**

**Gabbls, livvy94 and everyone else behind EarthBound Beginnings Remake had no
involvement in it** — they did not build it, review it, endorse it or ask for
it. Please do not report problems with this editor to them, and do not blame
them if it breaks your save.

None of which is a complaint — the opposite. EarthBound Beginnings Remake is
an incredible piece of work, and rebuilding Mother 1 inside EarthBound's engine
is an enormous undertaking. Huge thanks to Gabbls, livvy94 and everyone who has
put time into the project, and to Clyde "Tomato" Mandelin, whose work it builds
on. I only made this because I enjoyed the remake enough to want to poke around
inside it — I genuinely appreciate all the work that has gone into it.

## Found a bug?

Open an issue with what you did, what happened, and your `.srm` if you are
willing to share it — that makes almost anything reproducible in seconds.
Please do not attach a ROM or patch; this project ships no game data and
cannot accept any.

Ships no ROM, patch, or game data.
"""


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--force", action="store_true",
                   help="delete and recreate an existing release")
    p.add_argument("--notes-out", metavar="PATH",
                   help="write the release notes to PATH and exit; this is "
                        "how CI gets them, so there is one copy of the text")
    args = p.parse_args(argv)

    if args.notes_out:
        # Written here rather than piped, because the notes contain characters
        # a Windows console cannot encode and shell redirection would mangle
        # them (or fail outright).
        Path(args.notes_out).write_text(NOTES, encoding="utf-8")
        print(f"wrote {args.notes_out} ({len(NOTES.splitlines())} lines)")
        return 0

    tag = f"v{version()}"
    cli = gh()

    if run([cli, "auth", "status"], capture_output=True).returncode:
        sys.exit("gh is not authenticated. Run: gh auth login")

    if not EXE.is_file():
        print("executable missing; building it")
        if run([sys.executable, str(ROOT / "packaging" / "build_exe.py")]).returncode:
            return 1

    dirty = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                           capture_output=True, text=True).stdout.strip()
    if dirty:
        print("warning: working tree is dirty; the tag will point at HEAD, "
              "not at what is on disk:\n" + dirty)

    existing = run([cli, "release", "view", tag], capture_output=True)
    if existing.returncode == 0:
        if not args.force:
            sys.exit(f"release {tag} already exists; pass --force to replace")
        run([cli, "release", "delete", tag, "--yes", "--cleanup-tag"])

    notes = ROOT / "build" / "release_notes.md"
    notes.parent.mkdir(exist_ok=True)
    notes.write_text(NOTES, encoding="utf-8")

    rc = run([cli, "release", "create", tag,
              str(EXE), str(READ_ME),
              "--title", f"EBBR Save Editor {tag}",
              "--notes-file", str(notes)]).returncode
    if rc:
        return rc
    print(f"\npublished {tag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
