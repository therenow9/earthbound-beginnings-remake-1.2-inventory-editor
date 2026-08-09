import random
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from ebbr import layout as L                     # noqa: E402
from ebbr.sram import SaveFile, SaveError, sum16, xor16  # noqa: E402
from tools.make_fixture import build, build_blank, build_vanilla  # noqa: E402


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


# --- vanilla EarthBound discrimination ---------------------------------------
#
# The remake and vanilla share an identical header layout (data at +0x20,
# checksums at +0x1C/+0x1E) and differ only in block geometry. That makes the
# stride the sole discriminator, so it has to be tested from both sides.

def test_layout_constants_match_real_saves():
    """Pin the geometry to what real files actually contain.

    The fixture builders derive their bytes from these same constants, so every
    other layout test here stays self-consistent even if the numbers are wrong
    — which is how VANILLA shipped with data_offset 0x18 and checksums at
    0x14/0x16 through a fully passing suite. Only a hard-coded expectation
    catches that, so these values are transcribed from real saves:

      EBBR    - four independent remake saves
      VANILLA - a real stock EarthBound save, both mirrors of slot 0, sums
                C57F/E205 and C583/E201 over +0x20..+0x500

    Both games use the SAME header layout. Only stride and length differ.
    """
    assert (L.EBBR.data_offset, L.EBBR.ck_sum_at, L.EBBR.ck_xor_at) == (0x20, 0x1C, 0x1E)
    assert (L.EBBR.block_stride, L.EBBR.data_len) == (0x550, 0x530)

    assert (L.VANILLA.data_offset, L.VANILLA.ck_sum_at, L.VANILLA.ck_xor_at) == (0x20, 0x1C, 0x1E)
    assert (L.VANILLA.block_stride, L.VANILLA.data_len) == (0x500, 0x4E0)

    # Data must fill the block exactly, or blocks overlap or leave a gap.
    for lay in (L.EBBR, L.VANILLA):
        assert lay.block_len == lay.block_stride, lay.name


def test_detects_vanilla_layout():
    assert SaveFile(build_vanilla()).layout is L.VANILLA


def test_vanilla_blocks_validate():
    s = SaveFile(build_vanilla())
    assert len(s.populated) == 2       # 1 slot x 2 mirrors
    assert all(b.checksums_ok() for b in s.populated)


def test_ebbr_save_never_reads_as_vanilla():
    """Cross-check the discriminator in the direction that would corrupt data.

    Both layouts checksum from the same base offset, so the only thing keeping
    them apart is the span they cover. Misidentifying a remake save as vanilla
    would write 0x4E0-byte checksums over a 0x530-byte block.
    """
    s = SaveFile(build(seed=1, slots=2), layout=L.VANILLA)
    assert not any(b.checksums_ok() and not b.is_empty for b in s.blocks)


def test_vanilla_save_never_reads_as_ebbr():
    s = SaveFile(build_vanilla(), layout=L.EBBR)
    assert not any(b.checksums_ok() and not b.is_empty for b in s.blocks)


def test_cli_refuses_vanilla_save(tmp_path, capsys):
    """info must exit non-zero and say so, rather than decoding nonsense."""
    from ebbr.cli import main
    p = tmp_path / "vanilla.srm"
    p.write_bytes(build_vanilla())
    assert main(["info", str(p)]) == 1
    assert "not the remake" in capsys.readouterr().out


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
    assert ninten.hp == 200
    assert ninten.pp == 100


def test_inventory_length(save):
    inv = save.populated[0].character(0).inventory
    assert len(inv) == L.INVENTORY_SIZE
    assert inv[-1] == 0


def test_equipment_resolves_pointers(save):
    ch = save.populated[0].character(0)
    assert ch.equipment["weapon"] == ch.inventory[0]
    assert ch.equipment["body"] is None


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


def test_add_item_at_slot_inserts_rather_than_overwriting(save):
    """`--slot` means "put it here", not "write over whatever is here"."""
    ch = save.populated[0].character(0)
    before = ch.inventory
    ch.add_item(0x53, slot=0)
    assert ch.inventory[0] == 0x53
    assert ch.inventory[1:] == before[:-1]      # everything pushed down one


def test_add_item_rejects_a_slot_that_would_leave_a_gap(save):
    """Bags are contiguous in every real save; refuse to invent a hole."""
    ch = save.populated[0].character(0)
    for i in range(ch.item_count):
        ch.remove_item(0)
    ch.add_item(0x53)
    with pytest.raises(SaveError, match="gap"):
        ch.add_item(0x19, slot=5)


# --- removal, compaction, and equip-pointer maintenance ----------------------
#
# The game compacts bags when an item leaves and rewrites equip pointers to
# follow. Verified against two real saves: dropping Onyx hook from index 6 of
# Ninten's bag shifted everything after it down one, and moved his weapon
# pointer 12 -> 11 to keep pointing at Hank's bat.

def test_remove_item_compacts_the_bag(save):
    ch = save.populated[0].character(0)
    before = ch.inventory
    ch.remove_item(3)
    assert ch.inventory == before[:3] + before[4:] + [0]


def test_remove_item_shifts_equip_pointers_down(save):
    ch = save.populated[0].character(0)
    ch.equip_pointers = [5, 0, 0, 0]            # weapon <- bag slot 4
    equipped = ch.inventory[4]
    ch.remove_item(1)                           # before it, so it shifts
    assert ch.equip_pointers[0] == 4
    assert ch.equipment["weapon"] == equipped


def test_remove_item_unequips_what_it_removed(save):
    ch = save.populated[0].character(0)
    ch.equip_pointers = [3, 0, 0, 0]
    ch.remove_item(2)                           # the equipped slot itself
    assert ch.equip_pointers[0] == 0
    assert ch.equipment["weapon"] is None


def test_remove_item_leaves_earlier_pointers_alone(save):
    ch = save.populated[0].character(0)
    ch.equip_pointers = [1, 0, 0, 0]
    ch.remove_item(5)                           # after it
    assert ch.equip_pointers[0] == 1


def test_remove_rejects_empty_slot(save):
    ch = save.populated[0].character(0)
    with pytest.raises(SaveError, match="already empty"):
        ch.remove_item(L.INVENTORY_SIZE - 1)


def test_add_item_shifts_pointers_up(save):
    ch = save.populated[0].character(0)
    ch.remove_item(0)                           # make room
    ch.equip_pointers = [4, 0, 0, 0]
    equipped = ch.inventory[3]
    ch.add_item(0x53, slot=0)
    assert ch.equip_pointers[0] == 5
    assert ch.equipment["weapon"] == equipped


def test_swap_carries_equip_pointers(save):
    ch = save.populated[0].character(0)
    ch.equip_pointers = [1, 0, 0, 0]
    equipped = ch.inventory[0]
    ch.swap_slots(0, 4)
    assert ch.inventory[4] == equipped
    assert ch.equip_pointers[0] == 5
    assert ch.equipment["weapon"] == equipped


def test_swap_rejects_empty_slot(save):
    ch = save.populated[0].character(0)
    with pytest.raises(SaveError, match="empty"):
        ch.swap_slots(0, L.INVENTORY_SIZE - 1)


# --- level, experience and base stats ----------------------------------------

def test_level_round_trips(save):
    ch = save.populated[0].character(0)
    ch.level = 42
    assert ch.level == 42


def test_level_is_bounded(save):
    ch = save.populated[0].character(0)
    for bad in (0, 100):
        with pytest.raises(SaveError, match="level must be"):
            ch.level = bad


def test_exp_round_trips_across_the_full_range(save):
    """Experience is u24 — the real save's 1050480 needs all three bytes."""
    ch = save.populated[0].character(0)
    for value in (0, 1050480, L.EXP_MAX):
        ch.exp = value
        assert ch.exp == value


def test_exp_is_bounded(save):
    ch = save.populated[0].character(0)
    with pytest.raises(SaveError, match="experience must be"):
        ch.exp = L.EXP_MAX + 1


def test_exp_does_not_bleed_into_max_hp(save):
    """EXP ends at 0x09 and max HP starts at 0x0B; a u32 write would collide."""
    ch = save.populated[0].character(0)
    before = ch.hp_max
    ch.exp = L.EXP_MAX
    assert ch.hp_max == before


def test_level_and_exp_are_independent(save):
    ch = save.populated[0].character(0)
    ch.level = 7
    ch.exp = 123456
    assert (ch.level, ch.exp) == (7, 123456)


def test_every_stat_round_trips_independently(save):
    ch = save.populated[0].character(0)
    for n, name in enumerate(L.STATS):
        ch.set_stat(name, 100 + n)
    assert ch.stats == {name: 100 + n for n, name in enumerate(L.STATS)}


def test_stats_are_bounded(save):
    ch = save.populated[0].character(0)
    with pytest.raises(SaveError, match="0\\.\\.255"):
        ch.set_stat("speed", 256)


def test_unknown_stat_is_rejected(save):
    ch = save.populated[0].character(0)
    with pytest.raises(SaveError, match="unknown stat"):
        ch.set_stat("charisma", 10)


def test_stats_do_not_overlap_the_inventory(save):
    """Stats end at 0x1C, inventory starts at 0x24."""
    ch = save.populated[0].character(0)
    before = ch.inventory
    for name in L.STATS:
        ch.set_stat(name, 255)
    assert ch.inventory == before


# --- equip slots accept only their own category ------------------------------
#
# The game sorts its Equip menu by the item-type field in the ROM and will not
# offer a hamburger as a weapon, so writing one there produces a save it could
# not have made.

def test_equip_accepts_the_right_category(save):
    ch = save.populated[0].character(0)
    ch.add_item(0xE7, slot=1)                     # Silver sword
    assert ch.equip("weapon", 1) == 0xE7
    assert ch.equipment["weapon"] == 0xE7


def test_equip_refuses_a_consumable(save):
    ch = save.populated[0].character(0)
    ch.add_item(0x5A, slot=1)                     # Hamburger
    with pytest.raises(SaveError, match="not equipment"):
        ch.equip("weapon", 1)


def test_equip_refuses_gear_from_another_slot(save):
    ch = save.populated[0].character(0)
    ch.add_item(0x39, slot=1)                     # Rain pendant -> body
    with pytest.raises(SaveError, match="goes in the body slot"):
        ch.equip("arms", 1)


def test_a_refused_equip_changes_nothing(save):
    ch = save.populated[0].character(0)
    ch.add_item(0x5A, slot=1)
    before = ch.equip_pointers
    with pytest.raises(SaveError):
        ch.equip("weapon", 1)
    assert ch.equip_pointers == before


def test_equip_refuses_an_empty_slot(save):
    ch = save.populated[0].character(0)
    with pytest.raises(SaveError, match="empty"):
        ch.equip("weapon", L.INVENTORY_SIZE - 1)


def test_equip_rejects_an_unknown_slot_name(save):
    ch = save.populated[0].character(0)
    with pytest.raises(SaveError, match="not an equip slot"):
        ch.equip("trousers", 0)


def test_old_slot_names_still_work(save):
    """`pendant` was this project's name for what the game calls `body`."""
    ch = save.populated[0].character(0)
    ch.add_item(0x39, slot=1)
    ch.equip("pendant", 1)
    assert ch.equipment["body"] == 0x39


def test_unequip_clears_only_its_own_slot(save):
    ch = save.populated[0].character(0)
    ch.unequip("weapon")
    assert ch.equipment["weapon"] is None


# --- HP and PP are bounded by their maxima -----------------------------------

def test_hp_above_maximum_is_refused(save):
    ch = save.populated[0].character(0)
    with pytest.raises(SaveError, match="above"):
        ch.hp = ch.hp_max + 1


def test_pp_above_maximum_is_refused(save):
    ch = save.populated[0].character(0)
    with pytest.raises(SaveError, match="above"):
        ch.pp = ch.pp_max + 1


def test_hp_at_exactly_the_maximum_is_allowed(save):
    ch = save.populated[0].character(0)
    ch.hp = ch.hp_max
    assert ch.hp == ch.hp_max


def test_lowering_max_hp_pulls_current_down_with_it(save):
    ch = save.populated[0].character(0)
    ch.hp_max = 10
    assert ch.hp == 10, "current HP left stranded above the maximum"


def test_raising_max_hp_leaves_current_alone(save):
    ch = save.populated[0].character(0)
    before = ch.hp
    ch.hp_max = 900
    assert ch.hp == before


def test_max_hp_is_a_separate_field_from_current(save):
    ch = save.populated[0].character(0)
    ch.hp_max = 900
    ch.hp = 100
    assert (ch.hp, ch.hp_max) == (100, 900)


def test_stats_reject_values_past_the_display_width(save):
    ch = save.populated[0].character(0)
    with pytest.raises(SaveError, match="0\\.\\.999"):
        ch.hp_max = 1000


def test_bag_stays_contiguous_through_random_edits(save):
    """The invariant the game maintains; every operation must preserve it."""
    rng = random.Random(7)
    ch = save.populated[0].character(0)
    for _ in range(60):
        inv = ch.inventory
        n = ch.item_count
        op = rng.choice(["add", "take", "swap"])
        if op == "add" and n < L.INVENTORY_SIZE:
            ch.add_item(0x53, slot=rng.randrange(0, n + 1))
        elif op == "take" and n:
            ch.remove_item(rng.randrange(0, n))
        elif op == "swap" and n >= 2:
            ch.swap_slots(rng.randrange(0, n), rng.randrange(0, n))
        inv = ch.inventory
        filled = [i for i, v in enumerate(inv) if v]
        assert filled == list(range(len(filled))), f"hole in bag: {inv}"
        for p in ch.equip_pointers:
            assert p == 0 or inv[p - 1] != 0, "pointer into an empty slot"


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
