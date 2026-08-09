"""Checks that run against real saves when they are present.

Real saves cannot be committed, so every test here skips when saves/remake is
empty. They are worth having anyway: synthetic fixtures are built from the
same constants they validate, so only a real file can catch a wrong constant.

The in-game harness (tools/ingame_verify.py) is what proves the *game* accepts
an edit. These are the cheap offline half.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ebbr import layout as L                    # noqa: E402
from ebbr.sram import SaveFile                  # noqa: E402

REMAKE = sorted((ROOT / "saves" / "remake").glob("*.srm")) \
    if (ROOT / "saves" / "remake").is_dir() else []
VANILLA = sorted((ROOT / "saves" / "vanilla").glob("*")) \
    if (ROOT / "saves" / "vanilla").is_dir() else []

needs_remake = pytest.mark.skipif(not REMAKE, reason="no saves/remake/*.srm")
needs_vanilla = pytest.mark.skipif(not VANILLA, reason="no saves/vanilla/*")


@needs_remake
@pytest.mark.parametrize("path", REMAKE, ids=lambda p: p.stem[:28])
def test_real_remake_save_round_trips(path, tmp_path):
    """Load and rewrite a real save unchanged -> byte identical.

    The synthetic version of this test cannot catch a misread header, because
    it writes back whatever geometry it read. A real file can.
    """
    original = path.read_bytes()
    out = tmp_path / "out.srm"
    SaveFile(original).save(out)
    assert out.read_bytes() == original


@needs_remake
@pytest.mark.parametrize("path", REMAKE, ids=lambda p: p.stem[:28])
def test_real_remake_save_is_detected_and_valid(path):
    s = SaveFile.load(path)
    assert s.layout is L.EBBR
    assert s.populated, "no populated blocks"
    assert all(b.checksums_ok() for b in s.populated)


@needs_remake
@pytest.mark.parametrize("path", REMAKE, ids=lambda p: p.stem[:28])
def test_real_bags_are_contiguous(path):
    """The invariant our editing code maintains, checked against the source.

    If the game ever left a hole, add_item/remove_item would be modelling it
    wrong.
    """
    for blk in SaveFile.load(path).populated:
        for cid in range(L.CHAR_COUNT):
            inv = blk.character(cid).inventory
            filled = [i for i, v in enumerate(inv) if v]
            assert filled == list(range(len(filled))), \
                f"{L.CHARACTERS[cid]} has a hole: {inv}"


@needs_remake
@pytest.mark.parametrize("path", REMAKE, ids=lambda p: p.stem[:28])
def test_real_equip_pointers_resolve(path):
    """Every equip pointer must land on an occupied slot."""
    for blk in SaveFile.load(path).populated:
        for cid in range(L.CHAR_COUNT):
            ch = blk.character(cid)
            inv = ch.inventory
            for slot_name, p in zip(L.EQUIP_SLOTS, ch.equip_pointers):
                if p:
                    assert 1 <= p <= L.INVENTORY_SIZE
                    assert inv[p - 1] != 0, \
                        f"{L.CHARACTERS[cid]} {slot_name} -> empty slot {p}"


@needs_remake
@pytest.mark.parametrize("path", REMAKE, ids=lambda p: p.stem[:28])
def test_editing_a_real_save_touches_only_what_it_should(path, tmp_path):
    """An edit must change the bag, the pointers, and the checksums -- and
    nothing else anywhere in the file.

    Uses removal rather than insertion: it is the operation that shifts the
    whole tail of the bag and rewrites equip pointers, so it has the most
    scope to scribble somewhere it should not. It also always applies, where
    an insert cannot when a bag is already full.
    """
    original = path.read_bytes()
    s = SaveFile(original)
    s.edit_slot(0, lambda blk: blk.character(0).remove_item(0))
    out = tmp_path / "out.srm"
    s.save(out)
    edited = out.read_bytes()

    changed = {i for i in range(len(original)) if original[i] != edited[i]}
    allowed = set()
    for blk in s.slot(0):
        rec = blk._span.start + L.CHAR_TABLE
        allowed |= set(range(rec + L.INVENTORY, rec + L.INVENTORY + L.INVENTORY_SIZE))
        allowed |= set(range(rec + L.EQUIPMENT, rec + L.EQUIPMENT + L.EQUIPMENT_SIZE))
        allowed |= {blk.base + L.EBBR.ck_sum_at, blk.base + L.EBBR.ck_sum_at + 1,
                    blk.base + L.EBBR.ck_xor_at, blk.base + L.EBBR.ck_xor_at + 1}
    assert changed <= allowed, \
        f"unexpected bytes changed: {sorted(changed - allowed)[:10]}"


@needs_vanilla
@pytest.mark.parametrize("path", VANILLA, ids=lambda p: p.stem[:28])
def test_real_vanilla_save_is_recognised(path):
    """The case that exposed the wrong VANILLA geometry: a stock EarthBound
    save must be identified, not fail to load."""
    s = SaveFile.load(path)
    assert s.layout is L.VANILLA
    assert s.populated
    assert all(b.checksums_ok() for b in s.populated)


@needs_vanilla
@pytest.mark.parametrize("path", VANILLA, ids=lambda p: p.stem[:28])
def test_vanilla_save_is_refused_by_the_cli(path, capsys):
    from ebbr.cli import main
    assert main(["info", str(path)]) == 1
    assert "not the remake" in capsys.readouterr().out
