"""SRAM layout definitions.

Every offset here was measured against real save files, not taken from
documentation. See docs/FORMAT.md for the evidence behind each one and for
which fields are VERIFIED vs INFERRED.
"""

from dataclasses import dataclass

#: Written at the head of every save block, and also scattered at 0x500
#: intervals by EarthBound's anti-piracy SRAM probe at startup. Presence of
#: the signature does NOT imply a save exists at that offset.
SIGNATURE = b"HAL Laboratory, inc."

#: EB text encoding is ASCII biased by this amount.
TEXT_BIAS = 0x30


@dataclass(frozen=True)
class Layout:
    """Geometry of one SRAM save block."""

    name: str
    block_stride: int
    data_offset: int   # start of checksummed data, relative to block start
    data_len: int
    ck_sum_at: int     # sum-of-bytes checksum word, relative to block start
    ck_xor_at: int     # xor-of-words checksum word
    big_endian: bool = False

    @property
    def block_len(self) -> int:
        return self.data_offset + self.data_len


#: EarthBound Beginnings Remake. Confirmed against four independent saves.
EBBR = Layout(
    name="EBBR",
    block_stride=0x550,
    data_offset=0x20,
    data_len=0x530,
    ck_sum_at=0x1C,
    ck_xor_at=0x1E,
)

#: Stock EarthBound (USA). Included so the tool can recognise a vanilla save
#: and refuse it with a clear message rather than mangling it.
#:
#: The header layout is IDENTICAL to EBBR — same data offset, same checksum
#: words. Only the block geometry differs (0x500/0x4E0 here, 0x550/0x530 for
#: the remake). Confirmed against a real vanilla save: both mirror copies of
#: slot 0 match sum and xor exactly over +0x20..+0x500.
VANILLA = Layout(
    name="EarthBound (USA)",
    block_stride=0x500,
    data_offset=0x20,
    data_len=0x4E0,
    ck_sum_at=0x1C,
    ck_xor_at=0x1E,
)

KNOWN_LAYOUTS = (EBBR, VANILLA)


# --- fields within the data section -----------------------------------------

MONEY = 0x3C            # u32 LE
PARTY_ROSTER = 0x7A     # 1-based character ids, 0x00 terminated, max 4
NAME_TABLE = 0x513      # 4 entries
NAME_STRIDE = 7

CHAR_TABLE = 0x1D8      # 4 character records
CHAR_STRIDE = 0x5F      # 95 bytes
CHAR_COUNT = 4


# --- fields within a character record ---------------------------------------

INVENTORY = 0x24
INVENTORY_SIZE = 14

EQUIPMENT = 0x32
EQUIPMENT_SIZE = 4
#: Equip pointers are 1-based indices into the character's own inventory;
#: 0x00 means nothing equipped. Order confirmed across all 4 characters.
#:
#: These are the game's own names, read off its Equip screen. They were
#: previously "weapon, pendant, band, coin", which was a guess made from
#: whatever each character happened to have equipped — a pendant in slot 1, a
#: band in slot 2, a coin in slot 3. The order was right, the names were not.
#: Slot 3 in particular holds hats, ribbons and galoshes as well as coins,
#: which only makes sense once it is read as "Other".
EQUIP_SLOTS = ("weapon", "body", "arms", "other")

#: What the slots used to be called, so older commands keep working.
EQUIP_SLOT_ALIASES = {"pendant": "body", "band": "arms", "coin": "other"}


def resolve_equip_slot(name: str) -> str | None:
    """Canonical slot name for user input, or None if it is not a slot."""
    name = name.lower()
    name = EQUIP_SLOT_ALIASES.get(name, name)
    return name if name in EQUIP_SLOTS else None

#: Level, u8, and experience, u24 LE. VERIFIED: the experience bytes decode to
#: exactly the 1050480 the Status screen reports, and level tracks 50 -> 57
#: between the two real saves.
LEVEL = 0x06
EXP = 0x07
EXP_SIZE = 3
EXP_MAX = 0xFFFFFF

#: Base stats, one byte each. VERIFIED by writing a distinct value to every
#: byte of 0x16..0x23 at once and reading the Status screen back: the seven
#: below appeared, in this order.
#:
#: Offense and Defense are stored rather than derived, but the game recomputes
#: them whenever equipment changes — so an edit to those two lasts only until
#: the player next changes gear.
STATS = ("offense", "defense", "speed", "fight", "wisdom", "strength", "force")
STAT_OFFSETS = {name: 0x16 + i for i, name in enumerate(STATS)}
STAT_LIMIT = 255        # one byte each

CHAR_ID = 0x36

#: Current HP/PP, u16 LE. VERIFIED in-game: writing 777 here made the Status
#: screen read "Hit Points: 777 / 542".
HP_CUR = 0x48
PP_CUR = 0x4E

#: A second copy of HP/PP that equals the current value in every real save.
#: NOT the maxima. Purpose unknown. Written in step with the current values so
#: we never produce a pairing the game itself does not.
HP_ALT = 0x46
PP_ALT = 0x4C

#: Maximum HP/PP, u16 LE. VERIFIED in-game: writing 999/888 here made the
#: Status screen read "Hit Points: 123 / 999" and "Psychic Points: 234 / 888".
#: Also distinguishable in real saves — in the pre-Teddy save his current HP
#: is 0 while this field already holds 345, so the two cannot be the same
#: field even though every *active* character is at full health.
HP_MAX = 0x0B
PP_MAX = 0x0D
RECORD_TERMINATOR = 0x5D  # FF FF

#: Character ids as they index the name table.
CHARACTERS = ("Ninten", "Ana", "Lloyd", "Teddy")


def decode_text(raw: bytes) -> str:
    """Decode an EB-encoded string, stopping at the first terminator."""
    out = []
    for b in raw:
        if b == 0x00:
            break
        c = b - TEXT_BIAS
        out.append(chr(c) if 0x20 <= c < 0x7F else "?")
    return "".join(out)


def encode_text(s: str, length: int) -> bytes:
    """Encode to EB text, zero-padded to length. Raises if it will not fit."""
    if len(s) > length:
        raise ValueError(f"{s!r} exceeds {length} characters")
    return bytes(ord(c) + TEXT_BIAS for c in s).ljust(length, b"\x00")
