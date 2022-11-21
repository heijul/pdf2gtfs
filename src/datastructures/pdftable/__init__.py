""" Subpackage providing the low-level PDFTable. """
from typing import NamedTuple


Char = NamedTuple("Char",
                  [("x0", float), ("x1", float),
                   ("y0", float), ("y1", float),
                   ("text", str)])
