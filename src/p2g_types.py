""" Contains types used by multiple subpackages. """

from __future__ import annotations

from typing import NamedTuple


Char = NamedTuple("Char",
                  [("x0", float), ("x1", float),
                   ("y0", float), ("y1", float),
                   ("text", str)])
