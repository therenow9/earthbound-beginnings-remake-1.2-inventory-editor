"""Build the standalone Windows GUI executable.

    python packaging/build_exe.py

Produces dist/EBBR-Save-Editor.exe -- one file, no Python install needed.
The item table is bundled inside; `items._find_default_table` also looks for
a data/items.json beside the .exe first, so a corrected table can be dropped
in without a rebuild.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME = "EBBR-Save-Editor"


def main() -> int:
    table = ROOT / "data" / "items.json"
    if not table.is_file():
        print(f"missing {table}; run tools/extract_items.py first",
              file=sys.stderr)
        return 1

    for stale in (ROOT / "build", ROOT / "dist"):
        shutil.rmtree(stale, ignore_errors=True)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        "--onefile",
        # No console window: this is a GUI, and a stray terminal behind it
        # looks broken to anyone who did not start it from a shell.
        "--windowed",
        "--name", NAME,
        "--paths", str(ROOT / "src"),
        "--add-data", f"{table}{';' if sys.platform == 'win32' else ':'}data",
        # Nothing here uses these, and they add tens of MB apiece.
        "--exclude-module", "numpy",
        "--exclude-module", "PIL",
        "--exclude-module", "pytest",
        "--specpath", str(ROOT / "build"),
        str(ROOT / "packaging" / "gui_entry.py"),
    ]
    print(" ".join(cmd))
    rc = subprocess.call(cmd, cwd=ROOT)
    if rc:
        return rc

    exe = ROOT / "dist" / (NAME + (".exe" if sys.platform == "win32" else ""))
    if not exe.is_file():
        print("build reported success but produced no executable",
              file=sys.stderr)
        return 1
    print(f"\nbuilt {exe}  ({exe.stat().st_size / 1048576:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
