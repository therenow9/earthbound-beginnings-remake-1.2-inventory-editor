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
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.M)
    if not m:
        sys.exit("no version in pyproject.toml")
    return m.group(1)


NOTES = """\
First public release. Inventory and equipment editing for **EarthBound
Beginnings Remake**, with a GUI.

Download **EBBR-Save-Editor.exe** below and run it — nothing to install.
Read **RELEASE_README.md** for how to use it and where to find your save.

### What it does

- Edit each character's 14-slot bag: add, remove, reorder
- Set equipment: weapon, pendant, band, coin
- Edit current HP, PP and money
- Works on any of the three save slots
- Writes a `.bak` every time it saves

Levels, EXP, stats, PSI and story flags are deliberately left alone.

### Why you can trust it with your save

Saves written by this editor are loaded in an emulator and the game's own live
inventory is read back out of its RAM and compared byte for byte against what
was written — for every character. The Goods menu is checked too, including
which items still carry the `E` equipped marker. `tools/ingame_verify.py` in
the repo re-runs that check on demand.

It also keeps the two mirror copies each save slot contains in step and
recomputes both checksums, which is what makes the game accept the file.

Still: it is a save editor for a fan ROM hack. Keep the backup.

### Notes

- Windows will warn about an unknown publisher; the .exe is not code-signed.
- Vanilla EarthBound saves are refused on purpose — the remake changed the
  block geometry, and writing remake layout to a vanilla save would corrupt it.
- Close your emulator fully before editing. It writes SRAM out on exit and
  will overwrite your changes.

Ships no ROM, patch, or game data.
"""


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--force", action="store_true",
                   help="replace an existing tag and release")
    args = p.parse_args(argv)

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
