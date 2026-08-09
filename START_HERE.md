# Start here

This repo is scaffolded and its tests pass. Nothing is committed yet.

## First run

```bash
pip install -e ".[dev]"
pytest                       # expect 44 passed
git init && git add . && git commit -m "Initial commit: EBBR SRAM container layer"
```

## Then verify against real data

The synthetic fixtures prove the code is self-consistent; only a real save
proves the format is right.

```bash
ebbr info "<path to a real EBBR .srm>"
```

Expect: layout detected as EBBR, one or more slots `ok`, correct money and
party, and inventories whose named items match what the game shows.

If `info` reports layout `EarthBound (USA)`, that file is a vanilla save, not
a remake save.

If it errors with "contains no saves", the SRAM is blank — that is a
ROM/filename mismatch in the emulator, not a problem with the file format.

## Next task: Phase 2 in docs/PLAN.md

Populate the item table from a CoilSnake decompile of the patched ROM. This is
the only thing blocking a usable v1 — scope is inventory and equipment only.
Read `docs/PLAN.md` for the full plan and `docs/FORMAT.md` for what is already
known about the save format.

Two rules that matter:

1. Validate any imported item table with `items.check_against_known()`. It
   compares against 15 ids confirmed on two independent saves. A mismatch
   means the table was read wrong — stop, do not proceed.
2. Never commit ROMs, patches, or personal saves. `.gitignore` blocks them;
   leave those entries alone.
