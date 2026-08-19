"""Allow ``python -m deskapp`` to launch the GUI."""
from __future__ import annotations

from .app import main

raise SystemExit(main())
