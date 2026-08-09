"""Item table: extraction geometry, the safety gate, and the loaders.

No ROM is used here. read_table() is fed a synthetic image built from the same
EB text encoding a real ROM uses, so the tests exercise the decode and the
offset arithmetic without shipping game data.
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from ebbr import items, layout as L                    # noqa: E402
from tools.extract_items import (                      # noqa: E402
    ITEM_ENTRY_SIZE, read_table,
)


def fake_rom(names: dict[int, str], base: int = 0x1000) -> bytes:
    """A ROM-shaped buffer with `names` laid out at the real stride."""
    end = base + (max(names) + 1) * ITEM_ENTRY_SIZE
    buf = bytearray(end + ITEM_ENTRY_SIZE)
    for item_id, nm in names.items():
        at = base + item_id * ITEM_ENTRY_SIZE
        buf[at:at + len(nm)] = L.encode_text(nm, len(nm))
        # Records continue past the name with stats; the terminator is what
        # bounds the string, so leave plausible junk after it.
        buf[at + len(nm)] = 0x00
        buf[at + len(nm) + 1:at + ITEM_ENTRY_SIZE] = \
            bytes(range(1, ITEM_ENTRY_SIZE - len(nm)))
    return bytes(buf)


@pytest.fixture(autouse=True)
def restore_items():
    """ITEMS is module-level mutable state; keep tests from leaking into it."""
    saved = dict(items.ITEMS)
    yield
    items.ITEMS.clear()
    items.ITEMS.update(saved)


# --- extraction ---------------------------------------------------------------

def test_read_table_decodes_names_at_stride():
    names = {0x01: "Hamburger", 0x05: "Town map", 0x40: "Goddess band"}
    got = read_table(fake_rom(names), base=0x1000, count=0x41)
    assert got == names


def test_read_table_skips_blank_and_binary_entries():
    """Unused ids and non-text records must not become fake item names."""
    rom = bytearray(fake_rom({0x02: "Ocarina"}, base=0x1000))
    binary_at = 0x1000 + 0x03 * ITEM_ENTRY_SIZE
    rom[binary_at:binary_at + 8] = bytes([0x00, 0xFF, 0x01, 0xFE] * 2)
    got = read_table(bytes(rom), base=0x1000, count=0x10)
    assert got == {0x02: "Ocarina"}


def test_read_table_skips_id_zero():
    """0x00 is the empty-slot marker, not an item, however the ROM names it."""
    got = read_table(fake_rom({0x00: "Null", 0x01: "Pizza"}, base=0x1000),
                     base=0x1000, count=0x10)
    assert got == {0x01: "Pizza"}


def test_read_table_stops_at_end_of_rom():
    got = read_table(fake_rom({0x01: "Pizza"}, base=0x1000), base=0x1000, count=9999)
    assert got == {0x01: "Pizza"}


# --- the safety gate ----------------------------------------------------------

def test_check_against_known_passes_a_correct_table():
    table = {i: n for i, (n, _) in items.ITEMS.items()}
    assert items.check_against_known(table) == []


def test_check_against_known_catches_a_shifted_table():
    """The failure this exists to catch.

    An off-by-one-record base yields entirely real-looking names -- every entry
    is a genuine item, just the wrong one -- so nothing but a cross-check
    against independently established ids will notice.
    """
    table = {0x19: "Home-run bat", 0x39: "Flame pendant"}
    problems = items.check_against_known(table)
    assert len(problems) == 2
    assert "Hank's bat" in problems[0]


def test_check_against_known_ignores_rom_derived_entries():
    """Checking ROM names against a ROM import would be circular."""
    rom_ids = [i for i, (_, p) in items.ITEMS.items() if p == items.ROM]
    assert rom_ids, "expected some ROM-provenance entries"
    assert items.check_against_known({i: "Nonsense" for i in rom_ids}) == []


def test_check_against_known_ignores_unmentioned_ids():
    assert items.check_against_known({0x02: "Anything"}) == []


# --- loaders ------------------------------------------------------------------

def test_load_json_merges_and_overrides(tmp_path):
    p = tmp_path / "items.json"
    p.write_text(json.dumps({"0x01": "Teddy bear", "0x19": "Hank's bat"}))
    assert items.load_json(p) == 2
    assert items.name(0x01) == "Teddy bear"
    assert items.provenance(0x01) == items.ROM


def test_load_json_accepts_decimal_and_dict_forms(tmp_path):
    p = tmp_path / "items.json"
    p.write_text(json.dumps({
        "7": "Inhaler",
        "0x08": {"name": "Guessed", "provenance": items.INFERRED},
    }))
    items.load_json(p)
    assert items.name(0x07) == "Inhaler"
    assert items.provenance(0x08) == items.INFERRED


def test_load_default_is_not_fatal_when_missing(monkeypatch, tmp_path):
    """A missing table must degrade to the built-ins, never crash the CLI."""
    monkeypatch.setattr(items, "DEFAULT_TABLE", tmp_path / "nope.json")
    assert items.load_default() == 0
    assert items.name(0x19) == "Hank's bat"


def test_load_default_survives_a_corrupt_table(monkeypatch, tmp_path):
    p = tmp_path / "items.json"
    p.write_text("{ not json")
    monkeypatch.setattr(items, "DEFAULT_TABLE", p)
    assert items.load_default() == 0


def test_unknown_id_renders_as_hex():
    assert items.name(0x02) == "unknown 0x02"
    assert items.name(0) == "(empty)"
