"""Build a synthetic but structurally valid EBBR SRAM image.

Real saves cannot be committed (they are personal data tied to a ROM), so the
test suite generates its own fixtures instead. This produces an image with the
verified EBBR geometry, correct checksums, and plausible field values.
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ebbr import layout as L          # noqa: E402
from ebbr.sram import sum16, xor16    # noqa: E402

SRAM_SIZE = 0x2000


def build(seed: int = 0, slots: int = 1) -> bytes:
    rng = random.Random(seed)
    buf = bytearray(SRAM_SIZE)
    lay = L.EBBR

    # Signatures for all six blocks.
    for i in range(6):
        base = i * lay.block_stride
        if base + len(L.SIGNATURE) <= SRAM_SIZE:
            buf[base:base + len(L.SIGNATURE)] = L.SIGNATURE

    for slot in range(slots):
        data = bytearray(lay.data_len)

        data[L.MONEY:L.MONEY + 4] = (1234 + slot).to_bytes(4, "little")
        data[L.PARTY_ROSTER:L.PARTY_ROSTER + 4] = bytes([1, 2, 3, 4])

        for cid, nm in enumerate(L.CHARACTERS):
            off = L.NAME_TABLE + L.NAME_STRIDE * cid
            data[off:off + L.NAME_STRIDE] = L.encode_text(nm, L.NAME_STRIDE)

        for cid in range(L.CHAR_COUNT):
            rec = L.CHAR_TABLE + L.CHAR_STRIDE * cid
            hp = 200 + 50 * cid
            pp = 100 + 10 * cid
            for fld, val in ((L.HP_CUR, hp), (L.HP_MAX, hp),
                             (L.PP_CUR, pp), (L.PP_MAX, pp)):
                data[rec + fld:rec + fld + 2] = val.to_bytes(2, "little")
            data[rec + L.CHAR_ID] = cid

            # a partly-filled bag, last slot free
            inv = [rng.choice([0x19, 0x39, 0x5A, 0x6D, 0x82, 0xCA, 0xE0, 0xE5])
                   for _ in range(L.INVENTORY_SIZE - 1)] + [0]
            data[rec + L.INVENTORY:rec + L.INVENTORY + L.INVENTORY_SIZE] = bytes(inv)

            # weapon equipped from slot 1, rest empty
            data[rec + L.EQUIPMENT:rec + L.EQUIPMENT + L.EQUIPMENT_SIZE] = \
                bytes([1, 0, 0, 0])

            data[rec + L.RECORD_TERMINATOR:rec + L.RECORD_TERMINATOR + 2] = b"\xFF\xFF"

        # write both mirror copies
        for mirror in range(2):
            base = (slot * 2 + mirror) * lay.block_stride
            start = base + lay.data_offset
            buf[start:start + lay.data_len] = data
            buf[base + lay.ck_sum_at:base + lay.ck_sum_at + 2] = \
                sum16(data).to_bytes(2, "little")
            buf[base + lay.ck_xor_at:base + lay.ck_xor_at + 2] = \
                xor16(data).to_bytes(2, "little")

    return bytes(buf)


def build_blank() -> bytes:
    """A freshly initialised SRAM: signatures only, no saves.

    Mirrors what the anti-piracy startup probe leaves behind, at 0x500
    intervals rather than the save layout's stride.
    """
    buf = bytearray(SRAM_SIZE)
    for i in range(6):
        base = i * 0x500
        buf[base:base + len(L.SIGNATURE)] = L.SIGNATURE
    return bytes(buf)


if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "fixture.srm")
    out.write_bytes(build())
    print(f"wrote {out}")
