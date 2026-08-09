"""GUI tests.

These drive the real widgets — no mainloop, but real Tk objects, real
callbacks. The point is to catch the mistakes a GUI actually makes: editing
one mirror copy, forgetting to re-checksum, letting a stale widget value
overwrite the model, or leaving a bag in a state the game never produces.

Skipped where there is no display (headless CI); on Windows and macOS there
always is one.
"""

from __future__ import annotations

import pytest

tk = pytest.importorskip("tkinter")

from ebbr import items, layout as L                       # noqa: E402
from ebbr.gui import EditorApp, ItemPicker                # noqa: E402
from ebbr.sram import Character, SaveError, SaveFile      # noqa: E402

from tools.make_fixture import build                      # noqa: E402


@pytest.fixture(scope="module")
def root():
    try:
        r = tk.Tk()
    except tk.TclError as e:                              # pragma: no cover
        pytest.skip(f"no display: {e}")
    r.withdraw()
    yield r
    r.destroy()


@pytest.fixture(autouse=True)
def _no_modal_dialogs(monkeypatch):
    """Never let a test block on a message box.

    The GUI reports refusals through messagebox, which is modal — one
    unexpected error dialog and the whole suite hangs with no output. Record
    the calls instead so tests can assert on them.
    """
    seen: list[tuple[str, str]] = []
    for fn in ("showerror", "showinfo", "showwarning"):
        monkeypatch.setattr(f"ebbr.gui.messagebox.{fn}",
                            lambda title, msg, _s=seen, **k: _s.append((title, msg)))
    monkeypatch.setattr("ebbr.gui.messagebox.askyesno", lambda *a, **k: True)
    return seen


@pytest.fixture
def dialogs(_no_modal_dialogs):
    return _no_modal_dialogs


@pytest.fixture
def savefile(tmp_path):
    path = tmp_path / "test.srm"
    path.write_bytes(build())
    return path


@pytest.fixture
def app(root, savefile):
    items.load_default()
    a = EditorApp(root, str(savefile))
    yield a


def test_opens_and_shows_the_first_populated_slot(app, savefile):
    assert app.path == savefile
    assert app.block() is not None
    assert app.money.get() == str(app.block().money)


def test_refuses_a_vanilla_save(root, tmp_path, monkeypatch):
    """A stock EarthBound save must be rejected, not silently mangled."""
    from ebbr import layout

    raw = bytearray(8192)
    for i in range(2):
        base = i * layout.VANILLA.block_stride
        raw[base:base + len(layout.SIGNATURE)] = layout.SIGNATURE
        body = bytes(range(1, 33)) * 39
        body = body[:layout.VANILLA.data_len]
        raw[base + layout.VANILLA.data_offset:
            base + layout.VANILLA.data_offset + len(body)] = body
        data = raw[base + layout.VANILLA.data_offset:
                   base + layout.VANILLA.data_offset + layout.VANILLA.data_len]
        total = sum(data) & 0xFFFF
        acc = 0
        for k in range(0, len(data) - 1, 2):
            acc ^= data[k] | (data[k + 1] << 8)
        raw[base + layout.VANILLA.ck_sum_at:base + layout.VANILLA.ck_sum_at + 2] = \
            total.to_bytes(2, "little")
        raw[base + layout.VANILLA.ck_xor_at:base + layout.VANILLA.ck_xor_at + 2] = \
            (acc & 0xFFFF).to_bytes(2, "little")

    path = tmp_path / "vanilla.srm"
    path.write_bytes(bytes(raw))

    shown = {}
    monkeypatch.setattr("ebbr.gui.messagebox.showerror",
                        lambda title, msg, **k: shown.update(msg=msg))
    a = EditorApp(root)
    a.open(str(path))
    assert a.save is None
    assert "not the remake" in shown.get("msg", "")


# --- the invariants a GUI is most likely to break ---------------------------

def test_edit_updates_both_mirror_copies(app):
    """The game reads whichever copy validates; both must agree."""
    pane = app.panes[0]
    pane.listbox.selection_set(0)
    app.apply(lambda blk: blk.character(0).add_item(0x53), "add")

    mirrors = app.save.slot(app.slot)
    assert len(mirrors) == 2
    a, b = (m.character(0).inventory for m in mirrors)
    assert a == b
    assert 0x53 in a


def test_edit_leaves_checksums_valid(app):
    app.apply(lambda blk: blk.character(0).add_item(0x53), "add")
    for blk in app.save.slot(app.slot):
        assert blk.checksums_ok()


def test_removing_an_item_compacts_and_fixes_equipment(app):
    ch = app.block().character(0)
    ch.equip_pointers = [3, 0, 0, 0]
    equipped = ch.inventory[2]
    app.refresh()

    pane = app.panes[0]
    pane.listbox.selection_set(0)
    pane._remove()

    ch = app.block().character(0)
    inv = ch.inventory
    filled = [i for i, v in enumerate(inv) if v]
    assert filled == list(range(len(filled))), "GUI left a hole in the bag"
    assert ch.equipment["weapon"] == equipped, "equip pointer did not follow"


def test_move_down_swaps_and_keeps_selection(app):
    pane = app.panes[0]
    before = app.block().character(0).inventory
    pane.listbox.selection_set(0)
    pane._move(1)
    after = app.block().character(0).inventory
    assert after[0] == before[1] and after[1] == before[0]
    assert pane.listbox.curselection() == (1,)


def test_move_up_at_the_top_does_nothing(app):
    pane = app.panes[0]
    before = app.block().character(0).inventory
    pane.listbox.selection_set(0)
    pane._move(-1)
    assert app.block().character(0).inventory == before


def test_money_field_commits(app):
    app.money.set("12345")
    app._commit_money()
    assert app.block().money == 12345


def test_money_field_rejects_junk_without_touching_the_save(app):
    before = app.block().money
    app.money.set("not a number")
    app._commit_money()
    assert app.block().money == before
    assert app.money.get() == str(before)


def test_hp_field_commits_to_both_copies(app):
    pane = app.panes[0]
    pane.stat_vars["hp_max"].set("400")
    pane._commit_stat("hp_max")
    pane.stat_vars["hp"].set("321")
    pane._commit_stat("hp")
    ch = app.block().character(0)
    assert ch.hp == 321
    # The second copy tracks it; a stale one is a state the game never writes.
    assert ch.block.u16(ch.base + L.HP_ALT) == 321


def test_junk_in_a_stat_field_is_reverted(app):
    pane = app.panes[0]
    before = app.block().character(0).hp
    pane.stat_vars["hp"].set("not a number")
    pane._commit_stat("hp")
    assert app.block().character(0).hp == before
    assert pane.stat_vars["hp"].get() == str(before)


def test_equipment_dropdown_sets_the_pointer(app):
    """Put a second weapon in the bag, then equip it from the dropdown."""
    pane = app.panes[0]
    app.apply(lambda blk: blk.character(0).add_item(0xE7, slot=1),
              "add Silver sword")
    pane.equip["weapon"].set(f"1: {items.name(0xE7)}")
    pane._commit_equip("weapon")
    ch = app.block().character(0)
    assert ch.equip_pointers[0] == 2
    assert ch.equipment["weapon"] == 0xE7


def test_equipment_dropdown_can_clear(app):
    pane = app.panes[0]
    pane.equip["weapon"].set("(none)")
    pane._commit_equip("weapon")
    assert app.block().character(0).equip_pointers[0] == 0


# --- equip slots only accept what belongs in them ---------------------------

def test_dropdown_only_offers_items_that_fit_the_slot(app):
    """A hamburger must never even appear in the weapon list."""
    pane = app.panes[0]
    app.apply(lambda blk: blk.character(0).add_item(0x5A, slot=1),
              "add Hamburger")
    pane.refresh()

    offered = list(pane.equip["weapon"]["values"])
    assert "(none)" in offered
    assert not any("Hamburger" in o for o in offered)
    for entry in offered[1:]:
        slot_index = int(entry.split(":")[0])
        item_id = app.block().character(0).inventory[slot_index]
        assert items.equip_slot(item_id) == "weapon"


def test_every_dropdown_offers_only_its_own_category(app):
    pane = app.panes[0]
    pane.refresh()
    for slot_name in L.EQUIP_SLOTS:
        for entry in list(pane.equip[slot_name]["values"])[1:]:
            item_id = app.block().character(0).inventory[int(entry.split(":")[0])]
            assert items.equip_slot(item_id) == slot_name


def test_model_refuses_a_consumable_in_the_weapon_slot(app, dialogs):
    """Belt and braces: even if the widget were bypassed, the model says no."""
    ch = app.block().character(0)
    app.apply(lambda blk: blk.character(0).add_item(0x5A, slot=1), "add food")

    with pytest.raises(SaveError, match="cannot go in the weapon slot"):
        app.block().character(0).equip("weapon", 1)


def test_model_refuses_gear_in_the_wrong_gear_slot(app):
    """Rain pendant is body gear; it is still not a weapon."""
    app.apply(lambda blk: blk.character(0).add_item(0x39, slot=1),
              "add Rain pendant")
    with pytest.raises(SaveError, match="goes in the body slot"):
        app.block().character(0).equip("weapon", 1)


def test_wrong_slot_equip_leaves_the_save_untouched(app, dialogs):
    app.apply(lambda blk: blk.character(0).add_item(0x5A, slot=1), "add food")
    before = app.block().character(0).equip_pointers

    def do(blk):
        blk.character(0).equip("weapon", 1)

    assert app.apply(do, "should fail") is False
    assert app.block().character(0).equip_pointers == before
    assert dialogs, "the refusal should have been reported to the user"


# --- HP and PP are capped ----------------------------------------------------

def test_current_hp_is_capped_at_the_maximum(app):
    pane = app.panes[0]
    ceiling = app.block().character(0).hp_max
    pane.stat_vars["hp"].set(str(ceiling + 500))
    pane._commit_stat("hp")
    assert app.block().character(0).hp == ceiling


def test_current_pp_is_capped_at_the_maximum(app):
    pane = app.panes[0]
    ceiling = app.block().character(0).pp_max
    pane.stat_vars["pp"].set(str(ceiling + 500))
    pane._commit_stat("pp")
    assert app.block().character(0).pp == ceiling


def test_raising_the_maximum_then_current_works(app):
    pane = app.panes[0]
    pane.stat_vars["hp_max"].set("900")
    pane._commit_stat("hp_max")
    pane.stat_vars["hp"].set("850")
    pane._commit_stat("hp")
    ch = app.block().character(0)
    assert (ch.hp_max, ch.hp) == (900, 850)


def test_lowering_the_maximum_drags_current_down(app):
    pane = app.panes[0]
    pane.stat_vars["hp_max"].set("50")
    pane._commit_stat("hp_max")
    ch = app.block().character(0)
    assert ch.hp_max == 50
    assert ch.hp == 50, "current HP left above the new maximum"


def test_stats_are_clamped_to_the_display_width(app):
    pane = app.panes[0]
    pane.stat_vars["hp_max"].set("99999")
    pane._commit_stat("hp_max")
    assert app.block().character(0).hp_max == Character.STAT_MAX


def test_saving_writes_a_backup_and_a_loadable_file(app, savefile):
    original = savefile.read_bytes()
    app.apply(lambda blk: blk.character(0).add_item(0x53), "add")
    app.write()

    assert not app.dirty
    backups = list(savefile.parent.glob("test.srm.bak*"))
    assert backups, "no backup written"
    assert backups[0].read_bytes() == original

    reloaded = SaveFile.load_editable(savefile)
    assert 0x53 in reloaded.blocks[0].character(0).inventory
    for blk in reloaded.populated:
        assert blk.checksums_ok()


# --- typed-but-not-committed values must not be silently dropped ------------
#
# Entry widgets commit on Return or focus-out, and clicking the File menu does
# neither. "Type a number, then Save" was writing the old value.

def test_typing_money_then_saving_without_leaving_the_field(app, savefile):
    app.money.set("54321")
    app.write()
    assert SaveFile.load(savefile).blocks[0].money == 54321


def test_typing_hp_then_saving_without_leaving_the_field(app, savefile):
    pane = app.panes[0]
    pane.stat_vars["hp_max"].set("700")
    pane.stat_vars["hp"].set("650")
    app.write()
    ch = SaveFile.load(savefile).blocks[0].character(0)
    assert (ch.hp_max, ch.hp) == (700, 650)


def test_flush_applies_maxima_before_current_values(app):
    """Raising max and current together must not clamp against the old max."""
    pane = app.panes[0]
    ceiling = app.block().character(0).hp_max
    pane.stat_vars["hp"].set(str(ceiling + 200))
    pane.stat_vars["hp_max"].set(str(ceiling + 200))
    app.flush_pending()
    ch = app.block().character(0)
    assert ch.hp_max == ceiling + 200
    assert ch.hp == ceiling + 200, "current was clamped against the old maximum"


def test_typed_value_counts_as_an_unsaved_change(app):
    app.money.set("777")
    assert app._confirm_discard() is True    # patched askyesno returns True
    assert app.dirty, "typed edit was not registered before the discard check"


def test_switching_slot_does_not_move_a_typed_value(app):
    """A value typed for one slot must not land on another."""
    app.money.set("4242")
    app._slot_changed()
    assert app.block().money == 4242


def test_level_exp_and_stats_commit_from_the_gui(app, savefile):
    pane = app.panes[0]
    pane.stat_vars["level"].set("44")
    pane.stat_vars["exp"].set("777888")
    pane.stat_vars["speed"].set("123")
    app.write()

    ch = SaveFile.load(savefile).blocks[0].character(0)
    assert ch.level == 44
    assert ch.exp == 777888
    assert ch.stat("speed") == 123


def test_gui_clamps_level_and_stats(app):
    pane = app.panes[0]
    pane.stat_vars["level"].set("500")
    pane._commit_stat("level")
    assert app.block().character(0).level == 99

    pane.stat_vars["force"].set("9999")
    pane._commit_stat("force")
    assert app.block().character(0).stat("force") == L.STAT_LIMIT


def test_gui_accepts_exp_typed_with_commas(app):
    pane = app.panes[0]
    pane.stat_vars["exp"].set("1,050,480")
    pane._commit_stat("exp")
    assert app.block().character(0).exp == 1050480


def test_party_reorder_buttons_move_a_character(app):
    app.apply(lambda b: setattr(b, "party", [0, 1, 2]), "party")
    app.panes[1]._move_in_party(-1)
    assert app.block().party == [1, 0, 2]
    app.panes[1]._move_in_party(1)
    assert app.block().party == [0, 1, 2]


def test_reorder_buttons_are_disabled_at_the_ends(app):
    app.apply(lambda b: setattr(b, "party", [0, 1, 2]), "party")
    for pane in app.panes:
        pane.refresh()

    def off(button):
        return "disabled" in button.state()

    assert off(app.panes[0].earlier), "first member can still move earlier"
    assert not off(app.panes[0].later)
    assert not off(app.panes[2].earlier)
    assert off(app.panes[2].later), "last member can still move later"
    # Teddy is out of the party entirely.
    assert off(app.panes[3].earlier) and off(app.panes[3].later)


def test_reorder_at_the_edge_changes_nothing(app):
    app.apply(lambda b: setattr(b, "party", [0, 1, 2]), "party")
    app.panes[0]._move_in_party(-1)
    assert app.block().party == [0, 1, 2]


def test_saving_with_no_changes_is_byte_identical(app, savefile):
    original = savefile.read_bytes()
    app.write()
    assert savefile.read_bytes() == original


def test_revert_discards_changes(app, savefile):
    before = app.block().character(0).inventory
    app.apply(lambda blk: blk.character(0).add_item(0x53), "add")
    app.dirty = False          # skip the confirmation dialog
    app.revert()
    assert app.block().character(0).inventory == before


# --- item picker -------------------------------------------------------------

def test_picker_filters_by_name(root):
    items.load_default()
    picker = ItemPicker(root)
    try:
        picker.query.set("pendant")
        names = [n for _, n in picker.matches]
        assert names and all("pendant" in n.lower() for n in names)
    finally:
        picker.destroy()


def test_picker_filters_by_hex_id(root):
    items.load_default()
    picker = ItemPicker(root)
    try:
        picker.query.set("e5")
        assert 0xE5 in [i for i, _ in picker.matches]
    finally:
        picker.destroy()
