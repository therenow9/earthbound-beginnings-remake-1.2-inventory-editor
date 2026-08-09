import random
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from ebbr import layout as L                     # noqa: E402
from ebbr.sram import SaveFile, SaveError, sum16, xor16  # noqa: E402
from tools.make_fixture import build, build_blank        # noqa: E402


@pytest.fixture
def img():
    return build(seed=1, slots=2)


@pytest.fixture
def save(img):
    return SaveFile(img)


# --- the invariant that matters most ----------------------------------------

def test_roundtrip_is_byte_identical(img, tmp_path):
    """Load and write with no edits -> output must equal input exactly.

    This is the guard against silent corruption. If it ever fails, no other
    test result is trustworthy.
    """
    s = SaveFile(img)
    out = tmp_path / "out.srm"
    s.save(out)
    assert out.read_bytes() == img


def test_commit_without_edits_changes_nothing(img, tmp_path):
    s = SaveFile(img)
    s.commit()
    out = tmp_path / "out.srm"
    s.save(out)
    assert out.read_bytes() == img


# --- layout detection --------------------------------------------------------

def test_detects_ebbr_layout(save):
    assert save.layout is L.EBBR


def test_finds_six_blocks(save):
    assert len(save.blocks) == 6


def test_populated_blocks_validate(save):
    pops = save.populated
    assert len(pops) == 4          # 2 slots x 2 mirrors
    assert all(b.checksums_ok() for b in pops)


def test_empty_blocks_flagged_empty(save):
    empties = [b for b in save.blocks if b.is_empty]
    assert len(empties) == 2
    assert all(b.slot == 2 for b in empties)


def test_empty_block_does_not_drive_detection():
    """An all-zero block satisfies both checksums under every layout.

    A blank SRAM must therefore be reported as containing no saves, not
    silently 'detected' as some arbitrary layout with a bogus confidence.
    """
    with pytest.raises(SaveError, match="no non-empty save block"):
        SaveFile(build_blank(), layout=None)._detect()


def test_blank_sram_has_no_valid_blocks():
    """A blank image may contain stray signature bytes from the anti-piracy
    probe, so blocks are not necessarily all-zero under a given layout. The
    meaningful property is that none of them carry valid save data."""
    s = SaveFile(build_blank(), layout=L.EBBR)
    assert not any(b.checksums_ok() and not b.is_empty for b in s.blocks)


def test_rejects_non_sram():
    with pytest.raises(SaveError, match="signature"):
        SaveFile(b"\x00" * 0x2000)


# --- checksums ---------------------------------------------------------------

def test_checksum_detects_tampering(img):
    s = SaveFile(img)
    blk = s.populated[0]
    assert blk.checksums_ok()
    blk.write(L.MONEY, b"\xFF")
    assert not blk.checksums_ok()


def test_recompute_repairs(img):
    s = SaveFile(img)
    blk = s.populated[0]
    blk.write(L.MONEY, b"\xFF")
    blk.recompute_checksums()
    assert blk.checksums_ok()


@pytest.mark.parametrize("seed", range(20))
def test_random_byte_edit_only_touches_intended_bytes(img, seed):
    rng = random.Random(seed)
    s = SaveFile(img)
    blk = s.populated[0]
    off = rng.randrange(0x100, L.EBBR.data_len - 1)
    before = bytes(s.buf)
    blk.write(off, bytes([rng.randrange(1, 256)]))
    blk.recompute_checksums()
    changed = {i for i in range(len(before)) if before[i] != s.buf[i]}
    allowed = {blk._span.start + off}
    allowed |= {blk.base + L.EBBR.ck_sum_at, blk.base + L.EBBR.ck_sum_at + 1}
    allowed |= {blk.base + L.EBBR.ck_xor_at, blk.base + L.EBBR.ck_xor_at + 1}
    assert changed <= allowed
    assert blk.checksums_ok()


def test_xor16_ignores_trailing_odd_byte():
    assert xor16(b"\x01\x02\x03") == xor16(b"\x01\x02")
    assert sum16(b"\xFF\xFF") == 0x01FE


# --- field parsing -----------------------------------------------------------

def test_money(save):
    assert save.populated[0].money == 1234


def test_party_roster(save):
    assert save.populated[0].party == [0, 1, 2, 3]


def test_names(save):
    blk = save.populated[0]
    assert [blk.name(i) for i in range(4)] == list(L.CHARACTERS)


def test_character_stats(save):
    ninten = save.populated[0].character(0)
    assert ninten.name == "Ninten"
    assert ninten.hp == 200 and ninten.hp_max == 200
    assert ninten.pp == 100


def test_inventory_length(save):
    inv = save.populated[0].character(0).inventory
    assert len(inv) == L.INVENTORY_SIZE
    assert inv[-1] == 0


def test_equipment_resolves_pointers(save):
    ch = save.populated[0].character(0)
    assert ch.equipment["weapon"] == ch.inventory[0]
    assert ch.equipment["pendant"] is None


def test_equip_pointer_rejects_out_of_range(save):
    ch = save.populated[0].character(0)
    with pytest.raises(ValueError):
        ch.equip_pointers = [99, 0, 0, 0]


# --- editing -----------------------------------------------------------------

def test_add_item_uses_free_slot(save):
    ch = save.populated[0].character(0)
    slot = ch.add_item(0x53)
    assert slot == L.INVENTORY_SIZE - 1
    assert ch.inventory[slot] == 0x53


def test_add_item_rejects_full_bag(save):
    ch = save.populated[0].character(0)
    ch.add_item(0x53)
    with pytest.raises(SaveError, match="full"):
        ch.add_item(0x19)


def test_add_item_rejects_occupied_slot(save):
    ch = save.populated[0].character(0)
    with pytest.raises(SaveError, match="already holds"):
        ch.add_item(0x53, slot=0)


def test_edit_slot_updates_both_mirrors(img):
    """Both mirror copies must stay in step; the game reads either one."""
    s = SaveFile(img)
    s.edit_slot(0, lambda blk: blk.character(0).add_item(0x53))
    a, b = s.slot(0)
    assert a.character(0).inventory == b.character(0).inventory
    assert 0x53 in a.character(0).inventory
    assert a.checksums_ok() and b.checksums_ok()


def test_edit_slot_leaves_other_slots_alone(img):
    s = SaveFile(img)
    before = s.slot(1)[0].character(0).inventory
    s.edit_slot(0, lambda blk: blk.character(0).add_item(0x53))
    assert s.slot(1)[0].character(0).inventory == before
