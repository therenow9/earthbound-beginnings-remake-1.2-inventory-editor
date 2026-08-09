"""Prove an edited save actually loads in the game.

Synthetic tests show the code is self-consistent and a real save shows the
format was read right, but neither shows the *game* accepts what we wrote.
This drives BizHawk headless-ish: it injects a save, boots the ROM, loads the
file, and reads each character's live inventory back out of WRAM, then checks
it against what `ebbr info` predicts.

The comparison is the point. The game rebuilds its inventory from SRAM on
load, so if our bytes were wrong -- bad checksum, hole in the bag, dangling
equip pointer -- what comes back differs from what we wrote, or the save does
not load at all.

    python tools/ingame_verify.py --rom <rom> --save <srm>
    python tools/ingame_verify.py --rom <rom> --save <srm> \
        --edit "give Ninten 'Franklin badge'" --edit "take Ninten Hamburger"

Needs BizHawk (https://tasvideos.org/BizHawk), located via --bizhawk or the
EBBR_BIZHAWK environment variable. A GUI window opens while it runs.
"""

from __future__ import annotations

import argparse
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ebbr import cli, items, layout as L      # noqa: E402
from ebbr.sram import SaveFile                # noqa: E402

LUA = Path(__file__).resolve().parent / "ingame" / "verify.lua"


def find_bizhawk(explicit: str | None) -> Path:
    for cand in (explicit, os.environ.get("EBBR_BIZHAWK")):
        if cand:
            p = Path(cand)
            p = p if p.is_file() else p / "EmuHawk.exe"
            if p.is_file():
                return p
            raise SystemExit(f"no EmuHawk.exe at {cand}")
    raise SystemExit(
        "BizHawk not found. Pass --bizhawk <dir> or set EBBR_BIZHAWK.")


def expected_bags(path: Path) -> dict[int, str]:
    """What each character's bag should be, per our own parse of the save."""
    blk = SaveFile.load(path).blocks[0]
    out = {}
    for cid in range(L.CHAR_COUNT):
        inv = blk.character(cid).inventory
        if any(inv):
            out[cid] = "".join(f"{b:02X}" for b in inv)
    return out


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--rom", required=True)
    p.add_argument("--save", required=True)
    p.add_argument("--edit", action="append", default=[],
                   help="an ebbr command to apply first, minus the file "
                        "argument, e.g. \"give Ninten 'Magic coin'\"")
    p.add_argument("--bizhawk")
    p.add_argument("--shots", help="directory for screenshots")
    p.add_argument("--timeout", type=int, default=300)
    args = p.parse_args(argv)

    emuhawk = find_bizhawk(args.bizhawk)
    items.load_default()

    work = Path(tempfile.mkdtemp(prefix="ebbr_ingame_"))
    srm = work / "inject.srm"
    shutil.copy2(args.save, srm)

    # Apply the edits through the real CLI, so this tests the shipped path
    # rather than a parallel reimplementation of it.
    for edit in args.edit:
        argv_ = shlex.split(edit)
        argv_.insert(1, str(srm))
        argv_.append("--no-backup")
        print(f"$ ebbr {' '.join(argv_)}")
        rc = cli.main(argv_)
        if rc:
            print("edit failed; aborting", file=sys.stderr)
            return rc

    want = expected_bags(srm)
    if not want:
        print("no populated character bags in this save", file=sys.stderr)
        return 1

    shots = Path(args.shots) if args.shots else work / "shots"
    shots.mkdir(parents=True, exist_ok=True)

    result = work / "result.txt"
    job = work / "job.txt"
    # newline="" so Windows does not turn these into CRLF. A trailing \r ends
    # up inside the parsed paths and the Lua side fails on an error dialog
    # rather than exiting, which looks exactly like a hang.
    with open(job, "w", encoding="utf-8", newline="") as fh:
        fh.write(f"srm={srm.as_posix()}\n")
        fh.write(f"out={result.as_posix()}\n")
        fh.write(f"shots={shots.as_posix()}\n")
        for c, v in want.items():
            fh.write(f"bag{c}={v}\n")

    # Absolute paths only. EmuHawk runs with cwd set to its own directory, so
    # a relative ROM path resolves against the BizHawk folder, is not found,
    # and the process sits on a file-not-found dialog until the timeout.
    rom = Path(args.rom).resolve(strict=True)

    env = {**os.environ, "EBBR_JOB": str(job)}
    print(f"launching {emuhawk.name} ...")
    try:
        subprocess.run([str(emuhawk), f"--lua={LUA}", str(rom)],
                       cwd=emuhawk.parent, env=env, timeout=args.timeout,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        print("BizHawk timed out", file=sys.stderr)
        return 1

    if not result.exists():
        print("no result file — the Lua script did not run", file=sys.stderr)
        return 1

    report = dict(
        line.split("=", 1) for line in result.read_text().splitlines()
        if "=" in line)

    print()
    failures = 0
    for cid, expect in want.items():
        got = report.get(f"bag{cid}", "MISSING")
        name = L.CHARACTERS[cid]
        if got.startswith("FOUND"):
            addr, live = got.split("@")[1].split(" ")
            ok = live.upper() == expect.upper()
            print(f"  {name:7} WRAM 0x{addr}  {'OK' if ok else 'MISMATCH'}")
            if not ok:
                print(f"          wrote {expect}")
                print(f"          game  {live}")
                failures += 1
        else:
            failures += 1
            print(f"  {name:7} NOT FOUND in WRAM — the game did not load "
                  f"this bag as written")

    print(f"\nscreenshots: {shots}")
    if failures:
        print(f"FAILED: {failures} bag(s) did not match", file=sys.stderr)
        return 1
    print("PASS — the game loaded every bag exactly as written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
