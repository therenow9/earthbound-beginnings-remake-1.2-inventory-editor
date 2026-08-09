"""Item ID table.

The remake reassigned EarthBound's item ids, so vanilla tables are wrong here.

Every entry is tagged with how it was established. VERIFIED means the same id
was seen in two or more independent saves; ROM means it was read out of the
ROM's own item table; INFERRED is a single observation or a guess from context
and must not be trusted for writes without checking in-game first.

ROM and VERIFIED are kept apart on purpose rather than collapsed into one
"known good" tag: `check_against_known()` deliberately validates *only* the
VERIFIED entries, because checking ROM-derived names against a ROM import
would be circular and would prove nothing.

The full table is read straight out of the ROM's item table by
`tools/extract_items.py` into data/items.json, which overrides these built-ins
at startup. CoilSnake turned out to be unnecessary: the names sit at a fixed
stride in plain EB text. See docs/PLAN.md.

The hand-derived entries below are deliberately kept after that import. They
are what `check_against_known()` validates a fresh extraction against, so
deleting them would remove the only independent check that the table was read
at the right offset.
"""

from __future__ import annotations

import json
from pathlib import Path

VERIFIED = "verified"     # same id observed in >=2 independent saves
INFERRED = "inferred"     # single observation, or reasoned from context
ROM = "rom"               # read from the ROM's own item table

#: Where the generated table lands, relative to the repo root.
DEFAULT_TABLE = Path(__file__).resolve().parents[2] / "data" / "items.json"

#: id -> (name, provenance)
#:
#: Names marked INFERRED here were placeholders invented from the equip slot
#: they appeared in; the ROM has since supplied the real ones (noted inline).
#: They are left as-is because they record what a *save alone* could establish,
#: which is the baseline the ROM import is checked against.
ITEMS: dict[int, tuple[str, str]] = {
    0x19: ("Hank's bat",      VERIFIED),
    0x1E: ("Iron skillet",    ROM),        # was "Ana's weapon" (placeholder)
    0x28: ("Zip gun",         ROM),        # was "Lloyd's weapon" (placeholder)
    0x39: ("Rain pendant",    VERIFIED),
    0x3A: ("Flame pendant",   VERIFIED),
    0x3B: ("Earth pendant",   ROM),        # was "Lloyd's pendant" (placeholder)
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
    0xE6: ("Katana",          ROM),        # guessed from one save; ROM agrees
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


def _merge(raw: dict, default_provenance: str = ROM) -> int:
    """Merge a decoded table into ITEMS, overriding the built-ins.

    Accepts  {id: name}  or  {id: {name: ..., provenance: ...}}, with ids as
    ints or as strings in any base ("0xE5", "229").
    Returns the number of entries merged.
    """
    count = 0
    for key, val in (raw or {}).items():
        item_id = int(key, 0) if isinstance(key, str) else int(key)
        if isinstance(val, dict):
            ITEMS[item_id] = (val["name"], val.get("provenance", default_provenance))
        else:
            ITEMS[item_id] = (str(val), default_provenance)
        count += 1
    return count


def load_json(path: str | Path) -> int:
    """Merge the generated table from data/items.json. Stdlib only."""
    return _merge(json.loads(Path(path).read_text(encoding="utf-8")))


def load_yaml(path: str | Path) -> int:
    """Merge a YAML table. Needs the optional `yaml` extra.

    Kept for hand-maintained tables; the generated one is JSON so that the
    package has no required runtime dependencies.
    """
    import yaml  # optional dependency

    return _merge(yaml.safe_load(Path(path).read_text(encoding="utf-8")))


def load_default() -> int:
    """Load data/items.json if it is present. Returns 0 if it is not.

    Called at CLI startup. A missing or unreadable table must never be fatal —
    the built-ins below are enough to run, just with fewer names.
    """
    try:
        return load_json(DEFAULT_TABLE)
    except (OSError, ValueError):
        return 0


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
