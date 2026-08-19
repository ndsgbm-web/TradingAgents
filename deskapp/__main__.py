"""Allow the deskapp package to be launched as a script.

Two entry points:
* Dev mode:        ``python -m deskapp``        (package mode, __package__ set)
* PyInstaller:     ``TradingAgents-full.exe``   (onefile bootloader, no parent)

In PyInstaller onefile mode ``__main__.py`` runs at the bundle root with
``__package__`` empty, so ``from .app import main`` (relative) fails with
"attempted relative import with no known parent package". We side-step that
by adding the bundle's ``_MEIPASS`` to ``sys.path`` and importing the
``deskapp`` package by absolute name — which works in both modes.
"""
from __future__ import annotations

import sys
from pathlib import Path

# PyInstaller onefile: prepend the bundle's temp dir so absolute imports
# of ``deskapp.*`` resolve against the bundled package layout.
_MEIPASS = getattr(sys, "_MEIPASS", None)
if _MEIPASS:
    sys.path.insert(0, _MEIPASS)
# Belt-and-braces for ``python -m deskapp`` from the repo root: also ensure
# the parent of the ``deskapp`` package is on sys.path.
_PARENT = str(Path(__file__).resolve().parent.parent)
if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)

from deskapp.app import main  # noqa: E402  (sys.path mutation above)

raise SystemExit(main())
