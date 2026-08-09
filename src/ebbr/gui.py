"""Point-and-click save editor.

A thin shell over the same model the CLI drives. Every mutation goes through
`Character` (`add_item`, `remove_item`, `swap_slots`, `equip_pointers`) and
lands via `SaveFile.edit_slot`, which writes both mirror copies and
re-checksums them. That is deliberate: bag contiguity, equip-pointer fixup and
mirror consistency are enforced down in the model, so this file cannot get
them wrong by forgetting about them.

Edits apply to the in-memory image immediately, so what you see is always a
valid save; "Save" only flushes it to disk. There is no undo — the write makes
a .bak first, and Revert re-reads the file.

Run with `ebbr-gui`, or `python -m ebbr.gui`.
"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from . import items, layout as L
from .sram import Character, SaveError, SaveFile

APP_NAME = "EBBR Save Editor"

#: Extensions an emulator is likely to have written.
SAVE_TYPES = [("SNES save RAM", "*.srm *.sav"), ("All files", "*.*")]


class ItemPicker(tk.Toplevel):
    """Search-as-you-type chooser over the item table.

    There are 253 ids and the names collide heavily ("bat" matches a dozen),
    so a plain dropdown is unusable and this needs real filtering.
    """

    def __init__(self, parent, title="Choose an item"):
        super().__init__(parent)
        self.title(title)
        self.transient(parent)
        self.resizable(False, True)
        self.chosen: int | None = None

        self.query = tk.StringVar()
        entry = ttk.Entry(self, textvariable=self.query, width=34)
        entry.pack(fill="x", padx=8, pady=(8, 4))
        self.query.trace_add("write", lambda *_: self._refilter())

        frame = ttk.Frame(self)
        frame.pack(fill="both", expand=True, padx=8)
        self.listbox = tk.Listbox(frame, width=34, height=16,
                                  activestyle="dotbox", exportselection=False)
        bar = ttk.Scrollbar(frame, orient="vertical",
                            command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=bar.set)
        self.listbox.pack(side="left", fill="both", expand=True)
        bar.pack(side="right", fill="y")

        buttons = ttk.Frame(self)
        buttons.pack(fill="x", padx=8, pady=8)
        ttk.Button(buttons, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(buttons, text="Add", command=self._accept).pack(side="right", padx=4)

        self.listbox.bind("<Double-Button-1>", lambda _e: self._accept())
        self.listbox.bind("<Return>", lambda _e: self._accept())
        entry.bind("<Return>", lambda _e: self._accept())
        entry.bind("<Down>", lambda _e: (self.listbox.focus_set(), "break")[1])
        self.bind("<Escape>", lambda _e: self.destroy())

        self._refilter()
        entry.focus_set()
        self.grab_set()

    def _refilter(self) -> None:
        q = self.query.get().strip().lower()
        self.matches = [(i, n) for i, (n, _) in sorted(items.ITEMS.items())
                        if not q or q in n.lower() or q in f"{i:02x}"]
        self.listbox.delete(0, "end")
        for iid, name in self.matches:
            self.listbox.insert("end", f"0x{iid:02X}  {name}")
        if self.matches:
            self.listbox.selection_set(0)

    def _accept(self) -> None:
        sel = self.listbox.curselection()
        idx = sel[0] if sel else (0 if self.matches else None)
        if idx is None:
            return
        self.chosen = self.matches[idx][0]
        self.destroy()


class CharacterPane(ttk.Frame):
    """Bag, equipment and stats for one character."""

    def __init__(self, parent, app: "EditorApp", char_id: int):
        super().__init__(parent, padding=8)
        self.app = app
        self.char_id = char_id

        self.stat_vars: dict[str, tk.StringVar] = {}

        def field(parent, which, width=6):
            var = tk.StringVar()
            self.stat_vars[which] = var
            entry = ttk.Entry(parent, textvariable=var, width=width)
            entry.bind("<FocusOut>", lambda _e, w=which: self._commit_stat(w))
            entry.bind("<Return>", lambda _e, w=which: self._commit_stat(w))
            return entry

        vitals = ttk.Frame(self)
        vitals.pack(fill="x", pady=(0, 4))
        for label, cur_field, max_field in (("HP", "hp", "hp_max"),
                                            ("PP", "pp", "pp_max")):
            ttk.Label(vitals, text=label).pack(side="left")
            field(vitals, cur_field).pack(side="left", padx=(4, 0))
            ttk.Label(vitals, text="/").pack(side="left", padx=2)
            field(vitals, max_field).pack(side="left", padx=(0, 12))
        ttk.Label(vitals, text="current / maximum",
                  foreground="#777").pack(side="left", padx=4)

        progress = ttk.Frame(self)
        progress.pack(fill="x", pady=(0, 4))
        ttk.Label(progress, text="Level").pack(side="left")
        field(progress, "level", width=4).pack(side="left", padx=(4, 12))
        ttk.Label(progress, text="EXP").pack(side="left")
        field(progress, "exp", width=10).pack(side="left", padx=(4, 0))
        # The game computes stat growth in code, so we cannot follow a level
        # change with the stats it would have produced. Say so, rather than
        # let the level field look broken.
        ttk.Label(progress,
                  text="changing level does not adjust stats — set those below",
                  foreground="#777").pack(side="left", padx=12)

        base = ttk.LabelFrame(self, text="Stats", padding=6)
        base.pack(fill="x", pady=(0, 8))
        for name in L.STATS:
            cell = ttk.Frame(base)
            cell.pack(side="left", padx=(0, 10))
            ttk.Label(cell, text=name.title()).pack(side="top", anchor="w")
            field(cell, name, width=5).pack(side="top")
        ttk.Label(base, text="Offense and Defense are recalculated by the "
                             "game when equipment changes",
                  foreground="#777", wraplength=150,
                  justify="left").pack(side="left", padx=6)

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True)

        bag = ttk.LabelFrame(body, text="Bag", padding=6)
        bag.pack(side="left", fill="both", expand=True)
        self.listbox = tk.Listbox(bag, height=14, width=30,
                                  activestyle="dotbox", exportselection=False)
        self.listbox.pack(fill="both", expand=True)

        row = ttk.Frame(bag)
        row.pack(fill="x", pady=(6, 0))
        ttk.Button(row, text="Add…", command=self._add).pack(side="left")
        ttk.Button(row, text="Remove", command=self._remove).pack(side="left", padx=4)
        ttk.Button(row, text="▲", width=3, command=lambda: self._move(-1)).pack(side="left")
        ttk.Button(row, text="▼", width=3, command=lambda: self._move(1)).pack(side="left")

        gear = ttk.LabelFrame(body, text="Equipment", padding=6)
        gear.pack(side="left", fill="y", padx=(8, 0))
        self.equip: dict[str, ttk.Combobox] = {}
        for slot_name in L.EQUIP_SLOTS:
            line = ttk.Frame(gear)
            line.pack(fill="x", pady=2)
            ttk.Label(line, text=slot_name.title(), width=8).pack(side="left")
            combo = ttk.Combobox(line, state="readonly", width=22)
            combo.pack(side="left")
            combo.bind("<<ComboboxSelected>>",
                       lambda _e, s=slot_name: self._commit_equip(s))
            self.equip[slot_name] = combo

    # --- reading the model ---------------------------------------------------

    def character(self) -> Character | None:
        blk = self.app.block()
        return blk.character(self.char_id) if blk else None

    def refresh(self) -> None:
        ch = self.character()
        if ch is None:
            return
        keep = self.listbox.curselection()
        for which, var in self.stat_vars.items():
            var.set(str(ch.stat(which) if which in L.STAT_OFFSETS
                        else getattr(ch, which)))

        self.listbox.delete(0, "end")
        inv = ch.inventory
        for i, iid in enumerate(inv):
            label = f"{i:2d}  {items.name(iid)}" if iid else f"{i:2d}  —"
            self.listbox.insert("end", label)
        for i in range(len(inv)):
            if inv[i] == 0:
                self.listbox.itemconfigure(i, foreground="#999")

        # Each dropdown offers only what actually fits that slot, so a
        # hamburger is never presented as a weapon in the first place.
        pointers = ch.equip_pointers
        for idx, slot_name in enumerate(L.EQUIP_SLOTS):
            combo = self.equip[slot_name]
            combo["values"] = ["(none)"] + [
                f"{i}: {items.name(v)}" for i, v in enumerate(inv)
                if v and items.can_equip(v, slot_name)]
            p = pointers[idx]
            if 1 <= p <= L.INVENTORY_SIZE and inv[p - 1]:
                combo.set(f"{p - 1}: {items.name(inv[p - 1])}")
            else:
                combo.set("(none)")

        if keep and keep[0] < self.listbox.size():
            self.listbox.selection_set(keep[0])

    def _selected_slot(self) -> int | None:
        sel = self.listbox.curselection()
        return sel[0] if sel else None

    def typed(self) -> dict[str, str]:
        return {which: var.get() for which, var in self.stat_vars.items()}

    def flush(self, typed: dict[str, str] | None = None) -> None:
        """Commit anything typed but not yet applied.

        Takes the typed values as a snapshot because committing one field
        refreshes the pane, which rewrites every other box from the model and
        would otherwise discard the rest of what the user typed.
        """
        if self.character() is None:
            return
        typed = typed or self.typed()
        # Maxima first: raising a maximum has to land before the current value
        # that depends on it, or current gets clamped against the old ceiling.
        order = ["hp_max", "pp_max", "hp", "pp", "level", "exp", *L.STATS]
        for which in order:
            self.stat_vars[which].set(typed[which])
            self._commit_stat(which)

    # --- mutations -----------------------------------------------------------

    def _add(self) -> None:
        if self.character() is None:
            return
        picker = ItemPicker(self.app.root)
        self.app.root.wait_window(picker)
        if picker.chosen is None:
            return
        at = self._selected_slot()
        ch = self.character()
        # Selecting an occupied slot means "put it here"; otherwise append.
        where = at if at is not None and at < ch.item_count else None
        self.app.apply(
            lambda blk: blk.character(self.char_id).add_item(picker.chosen, where),
            f"added {items.name(picker.chosen)}")

    def _remove(self) -> None:
        slot = self._selected_slot()
        if slot is None:
            self.app.status("Select a bag slot first.")
            return
        self.app.apply(
            lambda blk: blk.character(self.char_id).remove_item(slot),
            f"removed bag slot {slot}")

    def _move(self, delta: int) -> None:
        slot = self._selected_slot()
        if slot is None:
            self.app.status("Select a bag slot first.")
            return
        target = slot + delta
        ch = self.character()
        if target < 0 or target >= ch.item_count:
            return
        self.app.apply(
            lambda blk: blk.character(self.char_id).swap_slots(slot, target),
            f"moved bag slot {slot} to {target}")
        self.listbox.selection_clear(0, "end")
        self.listbox.selection_set(target)

    #: Upper bound per editable field, and how to say its name.
    LIMITS = {"hp": Character.STAT_MAX, "hp_max": Character.STAT_MAX,
              "pp": Character.STAT_MAX, "pp_max": Character.STAT_MAX,
              "level": 99, "exp": L.EXP_MAX}
    LABELS = {"hp": "HP", "pp": "PP", "hp_max": "max HP", "pp_max": "max PP",
              "level": "level", "exp": "EXP"}

    def _commit_stat(self, which: str) -> None:
        ch = self.character()
        if ch is None:
            return
        var = self.stat_vars[which]
        is_base_stat = which in L.STAT_OFFSETS
        current = ch.stat(which) if is_base_stat else getattr(ch, which)

        raw = var.get().strip().replace(",", "")
        # Untouched box: leave it alone. Clamping applies to what the user
        # typed, never to what was already in the file — otherwise a save with
        # no edits would "correct" out-of-range values and stop being a no-op.
        if raw == str(current):
            return
        try:
            val = int(raw)
        except ValueError:
            var.set(str(current))
            return

        floor = 1 if which == "level" else 0
        ceiling = L.STAT_LIMIT if is_base_stat else self.LIMITS[which]
        val = max(floor, min(val, ceiling))

        # Current HP/PP cannot exceed the maximum. Clamp here rather than
        # letting the model reject it, so typing a big number snaps to the
        # cap instead of throwing a dialog at the user.
        note = ""
        if which in ("hp", "pp"):
            cap = getattr(ch, which + "_max")
            if val > cap:
                val, note = cap, f" (capped at {ch.name}'s maximum)"

        if val == current:
            var.set(str(current))
            return

        def do(blk):
            target = blk.character(self.char_id)
            if is_base_stat:
                target.set_stat(which, val)
            else:
                setattr(target, which, val)

        label = self.LABELS.get(which, which)
        if not self.app.apply(do, f"{ch.name} {label} = {val}{note}"):
            var.set(str(current))

    def _commit_equip(self, slot_name: str) -> None:
        ch = self.character()
        if ch is None:
            return
        choice = self.equip[slot_name].get()

        if choice == "(none)":
            self.app.apply(
                lambda blk: blk.character(self.char_id).unequip(slot_name),
                f"{ch.name}'s {slot_name} cleared")
            return

        bag_slot = int(choice.split(":")[0])
        self.app.apply(
            lambda blk: blk.character(self.char_id).equip(slot_name, bag_slot),
            f"{ch.name}'s {slot_name}: {items.name(ch.inventory[bag_slot])}")


class EditorApp:
    def __init__(self, root: tk.Tk, path: str | None = None):
        self.root = root
        self.save: SaveFile | None = None
        self.path: Path | None = None
        self.slot = 0
        self.dirty = False

        items.load_default()
        root.title(APP_NAME)
        # A bag holds at most 14 rows, so this is sized to show a full one
        # with the buttons and status bar visible and little slack. Tk scaling
        # inflates the fonts, hence the width.
        root.geometry("900x545")
        root.minsize(820, 480)
        self._build_menu()
        self._build_body()
        self._retitle()
        root.protocol("WM_DELETE_WINDOW", self.quit)
        if path:
            self.open(path)

    # --- chrome --------------------------------------------------------------

    def _build_menu(self) -> None:
        bar = tk.Menu(self.root)
        filemenu = tk.Menu(bar, tearoff=0)
        filemenu.add_command(label="Open…", accelerator="Ctrl+O",
                             command=self.open)
        filemenu.add_command(label="Save", accelerator="Ctrl+S",
                             command=self.write)
        filemenu.add_command(label="Save As…", command=self.write_as)
        filemenu.add_separator()
        filemenu.add_command(label="Revert", command=self.revert)
        filemenu.add_separator()
        filemenu.add_command(label="Exit", command=self.quit)
        bar.add_cascade(label="File", menu=filemenu)

        helpmenu = tk.Menu(bar, tearoff=0)
        helpmenu.add_command(label="About", command=self._about)
        bar.add_cascade(label="Help", menu=helpmenu)
        self.root.config(menu=bar)
        self.root.bind("<Control-o>", lambda _e: self.open())
        self.root.bind("<Control-s>", lambda _e: self.write())

    def _build_body(self) -> None:
        top = ttk.Frame(self.root, padding=(8, 8, 8, 0))
        top.pack(fill="x")
        ttk.Label(top, text="Save slot").pack(side="left")
        self.slot_combo = ttk.Combobox(top, state="readonly", width=10,
                                       values=[])
        self.slot_combo.pack(side="left", padx=(4, 16))
        self.slot_combo.bind("<<ComboboxSelected>>", self._slot_changed)

        ttk.Label(top, text="Money $").pack(side="left")
        self.money = tk.StringVar()
        money = ttk.Entry(top, textvariable=self.money, width=12)
        money.pack(side="left", padx=4)
        money.bind("<FocusOut>", lambda _e: self._commit_money())
        money.bind("<Return>", lambda _e: self._commit_money())

        self.tabs = ttk.Notebook(self.root, padding=8)
        self.tabs.pack(fill="both", expand=True)
        self.panes: list[CharacterPane] = []
        for cid in range(L.CHAR_COUNT):
            pane = CharacterPane(self.tabs, self, cid)
            self.tabs.add(pane, text=L.CHARACTERS[cid])
            self.panes.append(pane)

        self.statusbar = ttk.Label(self.root, anchor="w", relief="sunken",
                                   padding=(6, 3))
        self.statusbar.pack(fill="x", side="bottom")
        self.status("Open a .srm save to begin.")

    def _about(self) -> None:
        messagebox.showinfo(
            APP_NAME,
            f"{APP_NAME}\n\n"
            "Inventory and equipment editor for EarthBound Beginnings "
            "Remake.\n\nAlways keep a backup. A .bak is written on save, but "
            "a bad edit can still cost you a file.",
            parent=self.root)

    def status(self, text: str) -> None:
        self.statusbar.configure(text=text)

    def _retitle(self) -> None:
        name = self.path.name if self.path else "no file"
        self.root.title(f"{APP_NAME} — {name}{' *' if self.dirty else ''}")

    # --- model access --------------------------------------------------------

    def block(self):
        if not self.save:
            return None
        try:
            blocks = [b for b in self.save.slot(self.slot) if not b.is_empty]
        except SaveError:
            return None
        return blocks[0] if blocks else None

    def apply(self, fn, description: str) -> bool:
        """Run fn against both mirrors of the current slot, then refresh.

        Everything that mutates goes through here so no caller can forget
        edit_slot and leave the mirror copies disagreeing.
        """
        if not self.save:
            return False
        try:
            self.save.edit_slot(self.slot, fn)
        except SaveError as e:
            messagebox.showerror("Cannot do that", str(e), parent=self.root)
            self.refresh()
            return False
        self.dirty = True
        self._retitle()
        self.refresh()
        self.status(description)
        return True

    def refresh(self) -> None:
        blk = self.block()
        if blk is None:
            self.money.set("")
            for pane in self.panes:
                pane.listbox.delete(0, "end")
            return
        self.money.set(str(blk.money))
        party = set(blk.party)
        for cid, pane in enumerate(self.panes):
            pane.refresh()
            label = L.CHARACTERS[cid]
            self.tabs.tab(cid, text=label if cid in party else f"{label} (—)")

    def _commit_money(self) -> None:
        blk = self.block()
        if blk is None:
            return
        try:
            val = int(self.money.get().strip().replace(",", ""))
        except ValueError:
            self.money.set(str(blk.money))
            return
        if val == blk.money:
            return

        def do(b):
            b.money = val

        if not self.apply(do, f"money = ${val}"):
            self.money.set(str(blk.money))

    def _slot_changed(self, _event=None) -> None:
        choice = self.slot_combo.get()
        if not choice:
            return
        # Flush before switching, or a value typed for this slot would be
        # applied to the next one.
        self.flush_pending()
        self.slot = int(choice.split()[-1])
        self.refresh()

    # --- file operations -----------------------------------------------------

    def open(self, path: str | None = None) -> None:
        if not self._confirm_discard():
            return
        path = path or filedialog.askopenfilename(
            title="Open save", filetypes=SAVE_TYPES, parent=self.root)
        if not path:
            return
        try:
            save = SaveFile.load_editable(path)
        except SaveError as e:
            messagebox.showerror("Cannot open", str(e), parent=self.root)
            return
        except OSError as e:
            messagebox.showerror("Cannot open", str(e), parent=self.root)
            return

        populated = sorted({b.slot for b in save.populated})
        if not populated:
            messagebox.showerror(
                "Cannot open",
                "This SRAM contains no saves. That is usually a ROM/filename "
                "mismatch in the emulator rather than a problem with the "
                "file.", parent=self.root)
            return

        self.save, self.path, self.dirty = save, Path(path), False
        self.slot = populated[0]
        self.slot_combo["values"] = [f"Slot {n}" for n in populated]
        self.slot_combo.set(f"Slot {self.slot}")
        self._retitle()
        self.refresh()
        self.status(f"Loaded {self.path.name} — "
                    f"{len(populated)} populated slot(s).")

    def _backup(self, path: Path) -> Path:
        bak = path.with_suffix(path.suffix + ".bak")
        n = 1
        while bak.exists():
            bak = path.with_suffix(f"{path.suffix}.bak{n}")
            n += 1
        bak.write_bytes(path.read_bytes())
        return bak

    def flush_pending(self) -> None:
        """Apply edits still sitting in text boxes.

        Entry widgets only commit on Return or focus-out, and clicking a menu
        does neither — so "type a number, File > Save" silently saved the old
        value. Anything that writes to disk has to flush first.
        """
        if not self.save:
            return
        # Snapshot every box before committing anything: each commit refreshes
        # the whole window from the model, which would overwrite the boxes we
        # have not read yet.
        money = self.money.get()
        typed = [pane.typed() for pane in self.panes]

        self.money.set(money)
        self._commit_money()
        for pane, values in zip(self.panes, typed):
            pane.flush(values)

    def write(self) -> None:
        if not self.save or not self.path:
            return
        self.flush_pending()
        try:
            note = ""
            if self.path.exists():
                note = f" (backup: {self._backup(self.path).name})"
            self.save.save(self.path)
        except OSError as e:
            messagebox.showerror("Cannot save", str(e), parent=self.root)
            return
        self.dirty = False
        self._retitle()
        self.status(f"Saved {self.path.name}{note}")

    def write_as(self) -> None:
        if not self.save:
            return
        path = filedialog.asksaveasfilename(
            title="Save as", defaultextension=".srm", filetypes=SAVE_TYPES,
            parent=self.root)
        if not path:
            return
        self.path = Path(path)
        self.write()

    def revert(self) -> None:
        if not self.path:
            return
        if self.dirty and not messagebox.askyesno(
                "Revert", "Discard unsaved changes?", parent=self.root):
            return
        path = self.path
        self.dirty = False
        self.open(str(path))

    def _confirm_discard(self) -> bool:
        # Flush first so the dirty flag accounts for anything typed but not
        # yet committed; otherwise closing after typing a value reports no
        # unsaved changes and drops it without asking.
        self.flush_pending()
        if not self.dirty:
            return True
        return messagebox.askyesno(
            "Unsaved changes", "Discard unsaved changes?", parent=self.root)

    def quit(self) -> None:
        if self._confirm_discard():
            self.root.destroy()


def main(argv=None) -> int:
    import argparse

    p = argparse.ArgumentParser(prog="ebbr-gui", description=__doc__)
    p.add_argument("file", nargs="?", help="a .srm to open at startup")
    args = p.parse_args(argv)

    root = tk.Tk()
    try:
        root.call("tk", "scaling", 1.25)
    except tk.TclError:
        pass
    EditorApp(root, args.file)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
