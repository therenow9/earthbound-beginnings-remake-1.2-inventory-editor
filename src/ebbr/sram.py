"""SRAM container handling: blocks, checksums, and typed field access."""

from __future__ import annotations

from pathlib import Path

from . import items, layout as L


class SaveError(Exception):
    pass


# --- checksums ---------------------------------------------------------------

def sum16(data: bytes) -> int:
    return sum(data) & 0xFFFF


def xor16(data: bytes) -> int:
    acc = 0
    for i in range(0, len(data) - 1, 2):
        acc ^= data[i] | (data[i + 1] << 8)
    return acc & 0xFFFF


# --- blocks ------------------------------------------------------------------

class Block:
    """One save block. Slot N is stored twice, as mirror copies A and B."""

    def __init__(self, save: "SaveFile", index: int, base: int):
        self.save = save
        self.index = index
        self.base = base

    @property
    def slot(self) -> int:
        return self.index // 2

    @property
    def mirror(self) -> str:
        return "AB"[self.index % 2]

    @property
    def _span(self) -> slice:
        lay = self.save.layout
        start = self.base + lay.data_offset
        return slice(start, start + lay.data_len)

    @property
    def data(self) -> bytearray:
        return self.save.buf[self._span]

    @property
    def is_empty(self) -> bool:
        """An all-zero block is an unused slot.

        Important: such a block satisfies BOTH checksums under every candidate
        layout (0 == 0), so it must never be used as evidence when detecting
        the layout.
        """
        return not any(self.data)

    def _word(self, at: int) -> int:
        lay = self.save.layout
        raw = self.save.buf[self.base + at: self.base + at + 2]
        return int.from_bytes(raw, "big" if lay.big_endian else "little")

    def _set_word(self, at: int, val: int) -> None:
        lay = self.save.layout
        order = "big" if lay.big_endian else "little"
        self.save.buf[self.base + at: self.base + at + 2] = \
            (val & 0xFFFF).to_bytes(2, order)

    def checksums_ok(self) -> bool:
        lay = self.save.layout
        d = self.data
        return (self._word(lay.ck_sum_at) == sum16(d)
                and self._word(lay.ck_xor_at) == xor16(d))

    def recompute_checksums(self) -> None:
        lay = self.save.layout
        d = self.data
        self._set_word(lay.ck_sum_at, sum16(d))
        self._set_word(lay.ck_xor_at, xor16(d))

    # typed access ------------------------------------------------------------

    def read(self, off: int, size: int = 1) -> bytes:
        s = self._span.start + off
        return bytes(self.save.buf[s: s + size])

    def write(self, off: int, raw: bytes) -> None:
        s = self._span.start + off
        self.save.buf[s: s + len(raw)] = raw

    def u16(self, off: int) -> int:
        return int.from_bytes(self.read(off, 2), "little")

    def u32(self, off: int) -> int:
        return int.from_bytes(self.read(off, 4), "little")

    def set_u16(self, off: int, val: int) -> None:
        self.write(off, (val & 0xFFFF).to_bytes(2, "little"))

    def set_u32(self, off: int, val: int) -> None:
        self.write(off, (val & 0xFFFFFFFF).to_bytes(4, "little"))

    #: Widest value the money field can hold. The game shows far less than
    #: this, but the field itself is a u32 and nothing here needs to guess
    #: where the game's own display gives up.
    MONEY_MAX = 0xFFFFFFFF

    @property
    def money(self) -> int:
        return self.u32(L.MONEY)

    @money.setter
    def money(self, val: int) -> None:
        if not 0 <= val <= Block.MONEY_MAX:
            raise SaveError(f"money must be 0..{Block.MONEY_MAX}")
        self.set_u32(L.MONEY, val)

    @property
    def party(self) -> list[int]:
        """Party as 0-based character ids, in order."""
        raw = self.read(L.PARTY_ROSTER, 4)
        return [b - 1 for b in raw if b]

    @party.setter
    def party(self, char_ids: list[int]) -> None:
        """Set who is in the party, in order.

        The roster is only half of it — each character also carries an absent
        flag and a join marker, and an unrecruited one sits on 0 HP, so adding
        them by roster alone would put a corpse in the party. Verified against
        the pair of real saves that bracket Teddy joining.
        """
        if not char_ids:
            raise SaveError("the party cannot be empty")
        if len(char_ids) > L.CHAR_COUNT:
            raise SaveError(f"at most {L.CHAR_COUNT} characters")
        if len(set(char_ids)) != len(char_ids):
            raise SaveError("the same character twice")
        for cid in char_ids:
            if not 0 <= cid < L.CHAR_COUNT:
                raise SaveError(f"no character {cid}")

        self.write(L.PARTY_ROSTER,
                   bytes(c + 1 for c in char_ids).ljust(L.CHAR_COUNT, b"\x00"))
        for cid in range(L.CHAR_COUNT):
            self.character(cid)._set_present(cid in char_ids)

    def name(self, char_id: int) -> str:
        off = L.NAME_TABLE + L.NAME_STRIDE * char_id
        return L.decode_text(self.read(off, L.NAME_STRIDE))

    def character(self, char_id: int) -> "Character":
        return Character(self, char_id)

    @property
    def characters(self) -> list["Character"]:
        return [self.character(i) for i in range(L.CHAR_COUNT)]

    def __repr__(self) -> str:
        state = "empty" if self.is_empty else \
            ("ok" if self.checksums_ok() else "BAD")
        return f"<Block {self.index} slot{self.slot}{self.mirror} @0x{self.base:04X} {state}>"


class Character:
    """A character record inside a block."""

    def __init__(self, block: Block, char_id: int):
        self.block = block
        self.char_id = char_id
        self.base = L.CHAR_TABLE + L.CHAR_STRIDE * char_id

    @property
    def name(self) -> str:
        return self.block.name(self.char_id)

    #: HP and PP are u16, but the game's own displays are three digits wide.
    #: Values past this render as garbage even though they store fine.
    STAT_MAX = 999

    def _check_stat(self, what: str, val: int) -> int:
        if not 0 <= val <= Character.STAT_MAX:
            raise SaveError(f"{what} must be 0..{Character.STAT_MAX}")
        return val

    @property
    def in_party(self) -> bool:
        return self.char_id in self.block.party

    def _set_present(self, present: bool) -> None:
        """Bring a character into the party, or take them out of it.

        Called by Block.party, which owns the roster itself. Adding revives a
        character sitting on 0 HP — an unrecruited one always is, and the game
        would otherwise show them dead.
        """
        self.block.write(self.base + L.ABSENT_FLAG,
                         bytes([0 if present else 1]))
        self.block.write(self.base + L.JOIN_MARKER,
                         b"\x00\x00" if present else b"\xFF\xFF")
        if present and self.hp == 0:
            self.hp = self.hp_max
            if self.pp == 0:
                self.pp = self.pp_max

    @property
    def level(self) -> int:
        return self.block.read(self.base + L.LEVEL, 1)[0]

    @level.setter
    def level(self, val: int) -> None:
        if not 1 <= val <= 99:
            raise SaveError("level must be 1..99")
        self.block.write(self.base + L.LEVEL, bytes([val]))

    @property
    def exp(self) -> int:
        return int.from_bytes(
            self.block.read(self.base + L.EXP, L.EXP_SIZE), "little")

    @exp.setter
    def exp(self, val: int) -> None:
        if not 0 <= val <= L.EXP_MAX:
            raise SaveError(f"experience must be 0..{L.EXP_MAX}")
        self.block.write(self.base + L.EXP,
                         val.to_bytes(L.EXP_SIZE, "little"))

    def stat(self, name: str) -> int:
        try:
            return self.block.read(self.base + L.STAT_OFFSETS[name], 1)[0]
        except KeyError:
            raise SaveError(f"unknown stat {name!r}") from None

    def set_stat(self, name: str, val: int) -> None:
        if name not in L.STAT_OFFSETS:
            raise SaveError(f"unknown stat {name!r}")
        if not 0 <= val <= L.STAT_LIMIT:
            raise SaveError(f"{name} must be 0..{L.STAT_LIMIT}")
        self.block.write(self.base + L.STAT_OFFSETS[name], bytes([val]))

    @property
    def stats(self) -> dict[str, int]:
        return {name: self.stat(name) for name in L.STATS}

    @property
    def hp(self) -> int:
        return self.block.u16(self.base + L.HP_CUR)

    @hp.setter
    def hp(self, val: int) -> None:
        val = self._check_stat("HP", val)
        if val > self.hp_max:
            raise SaveError(
                f"HP {val} is above {self.name}'s maximum of {self.hp_max}; "
                f"raise max HP first")
        # Both copies, always. They are equal in every real save; leaving the
        # second one stale would create a pairing the game never writes.
        self.block.set_u16(self.base + L.HP_CUR, val)
        self.block.set_u16(self.base + L.HP_ALT, val)

    @property
    def hp_max(self) -> int:
        return self.block.u16(self.base + L.HP_MAX)

    @hp_max.setter
    def hp_max(self, val: int) -> None:
        val = self._check_stat("max HP", val)
        self.block.set_u16(self.base + L.HP_MAX, val)
        # Current can never exceed the new maximum.
        if self.hp > val:
            self.block.set_u16(self.base + L.HP_CUR, val)
            self.block.set_u16(self.base + L.HP_ALT, val)

    @property
    def pp(self) -> int:
        return self.block.u16(self.base + L.PP_CUR)

    @pp.setter
    def pp(self, val: int) -> None:
        val = self._check_stat("PP", val)
        if val > self.pp_max:
            raise SaveError(
                f"PP {val} is above {self.name}'s maximum of {self.pp_max}; "
                f"raise max PP first")
        self.block.set_u16(self.base + L.PP_CUR, val)
        self.block.set_u16(self.base + L.PP_ALT, val)

    @property
    def pp_max(self) -> int:
        return self.block.u16(self.base + L.PP_MAX)

    @pp_max.setter
    def pp_max(self, val: int) -> None:
        val = self._check_stat("max PP", val)
        self.block.set_u16(self.base + L.PP_MAX, val)
        if self.pp > val:
            self.block.set_u16(self.base + L.PP_CUR, val)
            self.block.set_u16(self.base + L.PP_ALT, val)

    @property
    def inventory(self) -> list[int]:
        return list(self.block.read(self.base + L.INVENTORY, L.INVENTORY_SIZE))

    @inventory.setter
    def inventory(self, ids: list[int]) -> None:
        if len(ids) != L.INVENTORY_SIZE:
            raise ValueError(f"inventory must be {L.INVENTORY_SIZE} entries")
        self.block.write(self.base + L.INVENTORY, bytes(ids))

    @property
    def free_slots(self) -> list[int]:
        return [i for i, v in enumerate(self.inventory) if v == 0]

    @property
    def equipment(self) -> dict[str, int | None]:
        """slot name -> item id, or None if that slot is empty."""
        ptrs = self.block.read(self.base + L.EQUIPMENT, L.EQUIPMENT_SIZE)
        inv = self.inventory
        out: dict[str, int | None] = {}
        for slot, p in zip(L.EQUIP_SLOTS, ptrs):
            out[slot] = inv[p - 1] if 1 <= p <= L.INVENTORY_SIZE else None
        return out

    @property
    def equip_pointers(self) -> list[int]:
        return list(self.block.read(self.base + L.EQUIPMENT, L.EQUIPMENT_SIZE))

    @equip_pointers.setter
    def equip_pointers(self, ptrs: list[int]) -> None:
        if len(ptrs) != L.EQUIPMENT_SIZE:
            raise ValueError(f"need {L.EQUIPMENT_SIZE} pointers")
        for p in ptrs:
            if not (0 <= p <= L.INVENTORY_SIZE):
                raise ValueError(f"equip pointer {p} out of range")
        self.block.write(self.base + L.EQUIPMENT, bytes(ptrs))

    @property
    def item_count(self) -> int:
        """Number of items held. Bags are contiguous, so this is also the
        index of the first free slot."""
        return sum(1 for v in self.inventory if v)

    def _shift_pointers(self, fn) -> None:
        """Rewrite equip pointers through fn(0-based index) -> new index|None.

        Equip pointers are 1-based indices into the bag, so any structural
        change to the bag has to move them in step or they end up pointing at
        the wrong item. Confirmed against real saves: when the game dropped an
        item from Ninten's bag, his weapon pointer moved 12 -> 11 to track it.
        """
        out = []
        for p in self.equip_pointers:
            if p == 0:
                out.append(0)
                continue
            new = fn(p - 1)
            # A pointer shifted off the end of the bag would be a dangling
            # reference; drop it to "nothing equipped" instead.
            if new is None or not 0 <= new < L.INVENTORY_SIZE:
                out.append(0)
            else:
                out.append(new + 1)
        self.equip_pointers = out

    def add_item(self, item_id: int, slot: int | None = None) -> int:
        """Insert an item, keeping the bag contiguous. Returns the slot used.

        `slot` inserts at that position and pushes the rest down rather than
        writing into a hole — the game never leaves holes (verified on eight
        real bags), so producing one would be inventing a state it cannot.
        """
        inv = self.inventory
        count = self.item_count
        if count >= L.INVENTORY_SIZE:
            raise SaveError(f"{self.name}'s inventory is full")
        if slot is None:
            slot = count
        elif not 0 <= slot <= count:
            raise SaveError(
                f"slot {slot} would leave a gap; {self.name} has {count} "
                f"item(s), so the last insertable slot is {count}")

        inv = inv[:slot] + [item_id] + inv[slot:]
        self.inventory = inv[:L.INVENTORY_SIZE]
        self._shift_pointers(lambda i: i + 1 if i >= slot else i)
        return slot

    def remove_item(self, slot: int) -> int:
        """Remove the item at `slot`, closing the gap. Returns the item id.

        Anything equipped from that slot becomes unequipped; anything after it
        shifts down, and its pointer follows. This mirrors what the game does
        when an item is used up.
        """
        inv = self.inventory
        if not 0 <= slot < L.INVENTORY_SIZE:
            raise SaveError(f"bag slot {slot} out of range")
        removed = inv[slot]
        if removed == 0:
            raise SaveError(f"bag slot {slot} is already empty")

        self.inventory = inv[:slot] + inv[slot + 1:] + [0]
        self._shift_pointers(
            lambda i: None if i == slot else (i - 1 if i > slot else i))
        return removed

    def swap_slots(self, a: int, b: int) -> None:
        """Exchange two bag slots, carrying any equip pointers with them.

        Both slots must hold something: swapping an item into an empty slot
        past the end of the bag would leave a hole, which the game never does.
        """
        inv = self.inventory
        for s in (a, b):
            if not 0 <= s < L.INVENTORY_SIZE:
                raise SaveError(f"bag slot {s} out of range")
            if inv[s] == 0:
                raise SaveError(f"bag slot {s} is empty; nothing to swap")
        inv[a], inv[b] = inv[b], inv[a]
        self.inventory = inv
        self._shift_pointers(lambda i: b if i == a else (a if i == b else i))

    def find_item(self, item_id: int) -> int | None:
        """First bag slot holding this id, or None."""
        for i, v in enumerate(self.inventory):
            if v == item_id:
                return i
        return None

    # --- equipment -----------------------------------------------------------
    #
    # Validation lives here rather than on the equip_pointers setter, which
    # has to stay permissive: the bag-shift logic rewrites pointers wholesale
    # and must not be second-guessed about item types while doing it.

    def equip(self, slot: str, bag_slot: int) -> int:
        """Equip whatever is in `bag_slot` into the named slot.

        Refuses items that do not belong there — the game sorts its own Equip
        menu by item type and will not offer a hamburger as a weapon, so
        writing one into the weapon slot produces a save it could not have
        made. Returns the item id equipped.
        """
        canonical = L.resolve_equip_slot(slot)
        if canonical is None:
            raise SaveError(
                f"{slot!r} is not an equip slot; expected one of "
                f"{', '.join(L.EQUIP_SLOTS)}")
        if not 0 <= bag_slot < L.INVENTORY_SIZE:
            raise SaveError(f"bag slot {bag_slot} out of range")

        item_id = self.inventory[bag_slot]
        if item_id == 0:
            raise SaveError(f"bag slot {bag_slot} is empty")

        actual = items.equip_slot(item_id)
        if actual != canonical:
            name = items.name(item_id)
            where = (f"it goes in the {actual} slot" if actual
                     else "it is not equipment")
            raise SaveError(
                f"{name} cannot go in the {canonical} slot — {where}")

        ptrs = self.equip_pointers
        ptrs[L.EQUIP_SLOTS.index(canonical)] = bag_slot + 1
        self.equip_pointers = ptrs
        return item_id

    def unequip(self, slot: str) -> None:
        canonical = L.resolve_equip_slot(slot)
        if canonical is None:
            raise SaveError(
                f"{slot!r} is not an equip slot; expected one of "
                f"{', '.join(L.EQUIP_SLOTS)}")
        ptrs = self.equip_pointers
        ptrs[L.EQUIP_SLOTS.index(canonical)] = 0
        self.equip_pointers = ptrs

    def __repr__(self) -> str:
        return f"<Character {self.name} HP {self.hp} PP {self.pp}>"


# --- file --------------------------------------------------------------------

class SaveFile:
    """An 8KB SRAM image containing up to three mirrored save slots."""

    def __init__(self, buf: bytes, layout: L.Layout | None = None):
        self.buf = bytearray(buf)
        self.block_offsets = self._scan()
        self.layout = layout or self._detect()

    @classmethod
    def load(cls, path: str | Path) -> "SaveFile":
        return cls(Path(path).read_bytes())

    @classmethod
    def load_editable(cls, path: str | Path) -> "SaveFile":
        """Load a save, refusing anything this tool must not write to.

        Vanilla EarthBound saves parse fine but have different block geometry;
        writing remake geometry over one corrupts it.
        """
        path = Path(path)
        s = cls.load(path)
        if s.layout is not L.EBBR:
            raise SaveError(
                f"{path.name} is a {s.layout.name} save, not the remake. "
                f"Editing it with this tool would corrupt it.")
        return s

    def save(self, path: str | Path) -> None:
        Path(path).write_bytes(bytes(self.buf))

    # detection ---------------------------------------------------------------

    def _scan(self) -> list[int]:
        offs, start = [], 0
        while True:
            i = self.buf.find(L.SIGNATURE, start)
            if i < 0:
                return offs
            offs.append(i)
            start = i + 1

    def _detect(self) -> L.Layout:
        """Pick the layout that validates the most NON-EMPTY blocks."""
        if not self.block_offsets:
            raise SaveError("no save-block signature found; not an SRAM image")

        best, best_hits = None, 0
        for lay in L.KNOWN_LAYOUTS:
            hits = 0
            for base in self.block_offsets:
                if base + lay.block_len > len(self.buf):
                    continue
                probe = SaveFile.__new__(SaveFile)
                probe.buf, probe.layout = self.buf, lay
                blk = Block(probe, 0, base)
                if not blk.is_empty and blk.checksums_ok():
                    hits += 1
            if hits > best_hits:
                best, best_hits = lay, hits

        if best is None:
            # No block carries valid save data, so the layout is simply not
            # determinable from this file.
            #
            # Do NOT try to infer it from block stride. EarthBound's
            # anti-piracy routine probes for SRAM at startup by writing the
            # signature at 0x500 intervals, so a save-less image shows
            # 0x500 spacing no matter which ROM produced it. Treating that
            # as layout evidence reads a startup artifact as structure.
            raise SaveError(
                "no non-empty save block found — this SRAM contains no saves. "
                "Signature spacing here is an anti-piracy startup artifact and "
                "does not identify the game; load a file with an actual save."
            )
        return best

    # blocks ------------------------------------------------------------------

    @property
    def blocks(self) -> list[Block]:
        return [Block(self, i, b) for i, b in enumerate(self.block_offsets)]

    @property
    def populated(self) -> list[Block]:
        return [b for b in self.blocks if not b.is_empty]

    def slot(self, n: int) -> list[Block]:
        """Both mirror copies of save slot n."""
        blks = [b for b in self.blocks if b.slot == n]
        if not blks:
            raise SaveError(f"slot {n} not present")
        return blks

    def commit(self) -> None:
        """Recompute checksums on every non-empty block."""
        for b in self.blocks:
            if not b.is_empty:
                b.recompute_checksums()

    def edit_slot(self, n: int, fn) -> None:
        """Apply fn(character_accessor) to BOTH mirror copies of a slot.

        Both copies must be kept in step; the game reads whichever validates.
        """
        for blk in self.slot(n):
            if blk.is_empty:
                continue
            fn(blk)
            blk.recompute_checksums()
