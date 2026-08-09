"""PyInstaller entry point.

`ebbr.gui` uses package-relative imports, so it cannot be handed to
PyInstaller as a bare script. This imports the package properly instead.
"""

from ebbr.gui import main

raise SystemExit(main())
