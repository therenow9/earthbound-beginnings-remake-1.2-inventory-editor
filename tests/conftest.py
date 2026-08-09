"""Shared test setup.

`items.ITEMS` is module-global and `load_default()` mutates it in place, so a
test that loads the real 253-entry table changes what every later test sees.
That is invisible when files are run one at a time and shows up as an
order-dependent failure in a full run. Snapshot and restore it around every
test so each one starts from the built-ins.
"""

import pytest

from ebbr import items


@pytest.fixture(autouse=True)
def _isolate_item_table():
    saved = dict(items.ITEMS)
    try:
        yield
    finally:
        items.ITEMS.clear()
        items.ITEMS.update(saved)
