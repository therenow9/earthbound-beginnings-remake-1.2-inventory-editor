"""Item ID table.

The remake reassigned EarthBound's item ids, so vanilla tables are wrong here.

The entries below were derived by hand from real saves and screenshots. Each
one is tagged with how it was established. Only entries confirmed against two
independent save files are marked VERIFIED — everything else is a working guess
and must not be trusted for writes without checking in-game first.

The full table should come from CoilSnake: decompile the patched ROM and read
the item names and indices out of the generated project data. Drop the result
in data/items.yml and it will override these built-ins. See docs/PLAN.md.
"""

from __future__ import annotations

from pathlib import Path

VERIFIED = "verified"     # same id observed in >=2 independent saves
INFERRED = "inferred"     # single observation, or reasoned from context

#: id -> (name, provenance)
ITEMS: dict[int, tuple[str, str]] = {
    0x19: ("Hank's bat",      VERIFIED),
    0x1E: ("Ana's weapon",    INFERRED),   # equipped weapon slot, name unknown
    0x28: ("Lloyd's weapon",  INFERRED),
    0x39: ("Rain pendant",    VERIFIED),
    0x3A: ("Flame pendant",   VERIFIED),
    0x3B: ("Lloyd's pendant", INFERRED),   # name unknown; id from equip slot
    0x53: ("Onyx hook",       VERIFIED),
    0x5A: ("Hamburger",       VERIFIED),
    0x6D: ("Life-up cream",   VERIFIED),
    0x79: ("Ocarina",         VERIFIED),
    0x82: ("Horn of life",    VERIFIED),
    0xAF: ("Bread loaf",      VERIFIED),
    0xB1: ("ATM card",        VERIFIED),
    0xCA: ("Town map",        VERIFIED),
    0xE0: ("Magic coin",      VERIFIED),
    0xE5: ("Goddess band",    VERIFIED),
    0xE6: ("Katana",          INFERRED),   # single save, equipped by Teddy
    0xEB: ("Breadcrumbs",     VERIFIED),
}


def name(item_id: int) -> str:
    if item_id == 0:
        return "(empty)"
    entry = ITEMS.get(item_id)
    return entry[0] if entry else f"unknown 0x{item_id:02X}"


def provenance(item_id: int) -> str | None:
    entry = ITEMS.get(item_id)
    return entry[1] if entry else None


def find(query: str) -> list[tuple[int, str]]:
    q = query.lower()
    return [(i, n) for i, (n, _) in sorted(ITEMS.items()) if q in n.lower()]


def load_yaml(path: str | Path) -> int:
    """Merge a CoilSnake-derived table, overriding the built-ins.

    Expected shape:  {id: name}  or  {id: {name: ..., provenance: ...}}
    Returns the number of entries loaded.
    """
    import yaml  # optional dependency; only needed once a table exists

    raw = yaml.safe_load(Path(path).read_text()) or {}
    count = 0
    for key, val in raw.items():
        item_id = int(key, 0) if isinstance(key, str) else int(key)
        if isinstance(val, dict):
            ITEMS[item_id] = (val["name"], val.get("provenance", VERIFIED))
        else:
            ITEMS[item_id] = (str(val), VERIFIED)
        count += 1
    return count


def check_against_known(table: dict[int, str]) -> list[str]:
    """Sanity-check a freshly imported table against our verified ids.

    A mismatch means the table was read wrong. Do not proceed past one.
    """
    problems = []
    for item_id, (known, prov) in ITEMS.items():
        if prov != VERIFIED:
            continue
        got = table.get(item_id)
        if got is not None and got.lower() != known.lower():
            problems.append(
                f"0x{item_id:02X}: imported {got!r} but verified as {known!r}"
            )
    return problems
