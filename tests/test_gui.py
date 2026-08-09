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
from ebbr.sram import SaveFile                            # noqa: E402

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
    pane.hp.set("321")
    pane._commit_stat("hp")
    ch = app.block().character(0)
    assert ch.hp == 321
    # The second copy tracks it; a stale one is a state the game never writes.
    assert ch.block.u16(ch.base + L.HP_ALT) == 321


def test_out_of_range_stat_is_refused_and_reverted(app, monkeypatch):
    monkeypatch.setattr("ebbr.gui.messagebox.showerror", lambda *a, **k: None)
    pane = app.panes[0]
    before = app.block().character(0).hp
    pane.hp.set("99999")
    pane._commit_stat("hp")
    assert app.block().character(0).hp == before
    assert pane.hp.get() == str(before)


def test_equipment_dropdown_sets_the_pointer(app):
    pane = app.panes[0]
    inv = app.block().character(0).inventory
    pane.equip["weapon"].set(f"1: {items.name(inv[1])}")
    pane._commit_equip("weapon")
    assert app.block().character(0).equip_pointers[0] == 2


def test_equipment_dropdown_can_clear(app):
    pane = app.panes[0]
    app.apply(lambda blk: setattr(blk.character(0), "equip_pointers",
                                  [1, 0, 0, 0]), "equip")
    pane.equip["weapon"].set("(none)")
    pane._commit_equip("weapon")
    assert app.block().character(0).equip_pointers[0] == 0


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
