"""Command line interface."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from . import items, layout as L
from .sram import SaveFile, SaveError


def _backup(path: Path) -> Path:
    bak = path.with_suffix(path.suffix + ".bak")
    n = 1
    while bak.exists():
        bak = path.with_suffix(f"{path.suffix}.bak{n}")
        n += 1
    shutil.copy2(path, bak)
    return bak


def cmd_info(args) -> int:
    s = SaveFile.load(args.file)
    print(f"{args.file}  ({len(s.buf)} bytes)")
    print(f"layout: {s.layout.name}  stride 0x{s.layout.block_stride:X}  "
          f"data +0x{s.layout.data_offset:02X} len 0x{s.layout.data_len:X}")
    if s.layout is L.VANILLA:
        print("\n!! This is a stock EarthBound save, not the remake. "
              "Editing it with this tool is not supported.")
        return 1
    print()
    for b in s.blocks:
        state = "empty" if b.is_empty else ("ok" if b.checksums_ok() else "BAD")
        print(f"  block {b.index}  0x{b.base:04X}  slot {b.slot}{b.mirror}  {state}")

    for slot in sorted({b.slot for b in s.populated}):
        blk = s.slot(slot)[0]
        print(f"\n--- slot {slot} ---")
        print(f"  money: ${blk.money}")
        print(f"  party: {', '.join(blk.name(c) for c in blk.party)}")
        for cid in range(L.CHAR_COUNT):
            ch = blk.character(cid)
            print(f"\n  {ch.name}  HP {ch.hp}/{ch.hp_max}  PP {ch.pp}/{ch.pp_max}")
            for i, iid in enumerate(ch.inventory):
                if iid:
                    print(f"     {i:2d}  0x{iid:02X}  {items.name(iid)}")
            eq = ch.equipment
            worn = [f"{k}={items.name(v)}" for k, v in eq.items() if v]
            print(f"     equipped: {', '.join(worn) if worn else '(none)'}")
    return 0


def cmd_diff(args) -> int:
    a = SaveFile.load(args.file_a)
    b = SaveFile.load(args.file_b or args.file_a)
    ba = a.blocks[args.block_a]
    bb = b.blocks[args.block_b]
    da, db = ba.data, bb.data
    n = min(len(da), len(db))
    diffs = [(i, da[i], db[i]) for i in range(n) if da[i] != db[i]]
    print(f"block {args.block_a} vs block {args.block_b}: {len(diffs)} differing byte(s)\n")
    for off, va, vb in diffs[:args.limit]:
        note = _describe_offset(off)
        print(f"  +0x{off:03X}  {va:02X} -> {vb:02X}   {note}")
    if len(diffs) > args.limit:
        print(f"  ... {len(diffs) - args.limit} more (raise --limit)")
    return 0


def _describe_offset(off: int) -> str:
    """Translate a raw data offset into a field name where we know one."""
    if off == L.MONEY or off in range(L.MONEY, L.MONEY + 4):
        return "money"
    if off in range(L.PARTY_ROSTER, L.PARTY_ROSTER + 4):
        return "party roster"
    if L.CHAR_TABLE <= off < L.CHAR_TABLE + L.CHAR_STRIDE * L.CHAR_COUNT:
        cid = (off - L.CHAR_TABLE) // L.CHAR_STRIDE
        rel = (off - L.CHAR_TABLE) % L.CHAR_STRIDE
        who = L.CHARACTERS[cid] if cid < len(L.CHARACTERS) else f"char{cid}"
        if L.INVENTORY <= rel < L.INVENTORY + L.INVENTORY_SIZE:
            return f"{who} inventory[{rel - L.INVENTORY}]"
        if L.EQUIPMENT <= rel < L.EQUIPMENT + L.EQUIPMENT_SIZE:
            return f"{who} equip[{L.EQUIP_SLOTS[rel - L.EQUIPMENT]}]"
        for fld, nm in ((L.HP_CUR, "hp"), (L.HP_MAX, "hp_max"),
                        (L.PP_CUR, "pp"), (L.PP_MAX, "pp_max")):
            if rel in (fld, fld + 1):
                return f"{who} {nm}"
        return f"{who} record +0x{rel:02X}"
    return ""


def _load_editable(path: Path) -> SaveFile:
    """Load a save, refusing anything this tool must not write to."""
    s = SaveFile.load(path)
    if s.layout is not L.EBBR:
        raise SystemExit(
            f"refusing to edit: {path.name} is a {s.layout.name} save, not "
            f"the remake. Writing remake geometry to it would corrupt it.")
    return s


def _write(s: SaveFile, path: Path, args) -> None:
    """Back up and save, unless this is a dry run.

    On a dry run the caller still prints what it would have done; main() adds
    the notice afterwards, so the summary reads as a prediction rather than
    being contradicted by a "nothing written" line above it.
    """
    if getattr(args, "dry_run", False):
        return
    if not args.no_backup:
        print(f"backup: {_backup(path)}")
    s.save(path)


def cmd_give(args) -> int:
    path = Path(args.file)
    s = _load_editable(path)
    cid = _resolve_char(args.character)
    item_id = _resolve_item(args.item)
    used = {}

    def edit(blk):
        used["slot"] = blk.character(cid).add_item(item_id, args.slot)

    s.edit_slot(args.save_slot, edit)
    _write(s, path, args)
    print(f"gave {items.name(item_id)} (0x{item_id:02X}) to "
          f"{L.CHARACTERS[cid]} in bag slot {used['slot']}")
    return 0


def _resolve_bag_slot(ch, token: str) -> int:
    """A bag slot given either as an index or as the name of an item in it."""
    if token.isdigit():
        return int(token)
    item_id = _resolve_item(token)
    slot = ch.find_item(item_id)
    if slot is None:
        raise SystemExit(
            f"{ch.name} is not carrying {items.name(item_id)} "
            f"(0x{item_id:02X})")
    return slot


def cmd_take(args) -> int:
    path = Path(args.file)
    s = _load_editable(path)
    cid = _resolve_char(args.character)
    taken = {}

    def edit(blk):
        ch = blk.character(cid)
        slot = _resolve_bag_slot(ch, args.item)
        taken["id"] = ch.remove_item(slot)
        taken["slot"] = slot

    s.edit_slot(args.save_slot, edit)
    _write(s, path, args)
    print(f"took {items.name(taken['id'])} (0x{taken['id']:02X}) from "
          f"{L.CHARACTERS[cid]} bag slot {taken['slot']}")
    return 0


def cmd_swap(args) -> int:
    path = Path(args.file)
    s = _load_editable(path)
    cid = _resolve_char(args.character)

    def edit(blk):
        ch = blk.character(cid)
        ch.swap_slots(_resolve_bag_slot(ch, args.a), _resolve_bag_slot(ch, args.b))

    s.edit_slot(args.save_slot, edit)
    _write(s, path, args)
    print(f"swapped {L.CHARACTERS[cid]}'s bag slots {args.a} and {args.b}")
    return 0


def cmd_unequip(args) -> int:
    path = Path(args.file)
    s = _load_editable(path)
    cid = _resolve_char(args.character)
    if args.slot_name not in L.EQUIP_SLOTS:
        print(f"slot must be one of {', '.join(L.EQUIP_SLOTS)}", file=sys.stderr)
        return 1
    idx = L.EQUIP_SLOTS.index(args.slot_name)

    def edit(blk):
        ch = blk.character(cid)
        ptrs = ch.equip_pointers
        ptrs[idx] = 0
        ch.equip_pointers = ptrs

    s.edit_slot(args.save_slot, edit)
    _write(s, path, args)
    print(f"unequipped {L.CHARACTERS[cid]}'s {args.slot_name}")
    return 0


def cmd_equip(args) -> int:
    path = Path(args.file)
    s = _load_editable(path)
    cid = _resolve_char(args.character)
    if args.slot_name not in L.EQUIP_SLOTS:
        print(f"slot must be one of {', '.join(L.EQUIP_SLOTS)}", file=sys.stderr)
        return 1
    idx = L.EQUIP_SLOTS.index(args.slot_name)
    used = {}

    def edit(blk):
        ch = blk.character(cid)
        slot = _resolve_bag_slot(ch, args.bag_slot)
        inv = ch.inventory
        if not (0 <= slot < L.INVENTORY_SIZE) or inv[slot] == 0:
            raise SaveError(f"bag slot {slot} is empty")
        ptrs = ch.equip_pointers
        ptrs[idx] = slot + 1
        ch.equip_pointers = ptrs
        used["slot"] = slot
        used["id"] = inv[slot]

    s.edit_slot(args.save_slot, edit)
    _write(s, path, args)
    print(f"equipped {L.CHARACTERS[cid]}'s {args.slot_name}: "
          f"{items.name(used['id'])} from bag slot {used['slot']}")
    return 0


def cmd_items(args) -> int:
    #: Only call out what the user should be careful with. ROM-derived names
    #: are the common case now, so flagging them would be noise.
    flags = {items.INFERRED: "   (inferred)"}
    n = 0
    for iid, (nm, prov) in sorted(items.ITEMS.items()):
        if args.query and args.query.lower() not in nm.lower():
            continue
        print(f"  0x{iid:02X}  {nm}{flags.get(prov, '')}")
        n += 1
    if args.query and not n:
        print(f"  no item matching {args.query!r}")
    return 0


def _resolve_char(token: str) -> int:
    if token.isdigit():
        return int(token)
    for i, nm in enumerate(L.CHARACTERS):
        if nm.lower() == token.lower():
            return i
    raise SystemExit(f"unknown character {token!r}")


def _resolve_item(token: str) -> int:
    try:
        return int(token, 0)
    except ValueError:
        pass
    hits = items.find(token)
    if not hits:
        raise SystemExit(f"unknown item {token!r} (try `ebbr items`)")
    if len(hits) == 1:
        return hits[0][0]

    # With the full 253-entry table loaded, substring matches collide
    # constantly ("bomb" hits several bats and bombs). An exact name is
    # unambiguous by definition, so let it win over its own superstrings.
    exact = [(i, n) for i, n in hits if n.lower() == token.lower()]
    if len(exact) == 1:
        return exact[0][0]

    shown = ", ".join(f"{n} (0x{i:02X})" for i, n in hits[:8])
    more = f", and {len(hits) - 8} more" if len(hits) > 8 else ""
    raise SystemExit(f"ambiguous: {shown}{more}\n"
                     f"give the exact name or the id")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="ebbr", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    pi = sub.add_parser("info", help="summarise a save file")
    pi.add_argument("file")
    pi.set_defaults(func=cmd_info)

    pd = sub.add_parser("diff", help="compare two blocks, with field names")
    pd.add_argument("file_a")
    pd.add_argument("block_a", type=int)
    pd.add_argument("block_b", type=int)
    pd.add_argument("--file-b")
    pd.add_argument("--limit", type=int, default=60)
    pd.set_defaults(func=cmd_diff)

    def editing_parser(name, help_):
        sp = sub.add_parser(name, help=help_)
        sp.add_argument("file")
        sp.add_argument("character", help="name or index, e.g. Ninten or 0")
        sp.add_argument("--save-slot", type=int, default=0)
        sp.add_argument("--no-backup", action="store_true")
        sp.add_argument("-n", "--dry-run", action="store_true",
                        help="report what would change, write nothing")
        return sp

    pg = editing_parser("give", "put an item in a character's bag")
    pg.add_argument("item", help="name or id, e.g. 'Goddess band' or 0xE5")
    pg.add_argument("--slot", type=int,
                    help="insert at this bag slot, pushing the rest down "
                         "(default: append)")
    pg.set_defaults(func=cmd_give)

    pk = editing_parser("take", "remove an item, closing the gap")
    pk.add_argument("item", help="bag slot number, or the item's name")
    pk.set_defaults(func=cmd_take)

    pw = editing_parser("swap", "exchange two bag slots")
    pw.add_argument("a", help="bag slot number, or item name")
    pw.add_argument("b", help="bag slot number, or item name")
    pw.set_defaults(func=cmd_swap)

    pe = editing_parser("equip", "point an equip slot at a bag slot")
    pe.add_argument("slot_name", help=" | ".join(L.EQUIP_SLOTS))
    pe.add_argument("bag_slot", help="bag slot number, or item name")
    pe.set_defaults(func=cmd_equip)

    pu = editing_parser("unequip", "clear an equip slot")
    pu.add_argument("slot_name", help=" | ".join(L.EQUIP_SLOTS))
    pu.set_defaults(func=cmd_unequip)

    pt = sub.add_parser("items", help="list known item ids")
    pt.add_argument("query", nargs="?")
    pt.set_defaults(func=cmd_items)

    args = p.parse_args(argv)
    items.load_default()   # data/items.json if present; harmless if not
    try:
        rc = args.func(args)
    except SaveError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    if not rc and getattr(args, "dry_run", False):
        print("(dry run — nothing was written)")
    return rc


if __name__ == "__main__":
    sys.exit(main())
