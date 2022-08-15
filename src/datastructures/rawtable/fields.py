from __future__ import annotations

import pandas as pd

from datastructures.rawtable.bbox import BBox, BBoxObject
from datastructures.rawtable.container import (
    Column, FieldColumnReference, FieldRowReference, Row)


class Field(BBoxObject):
    row: Row = FieldRowReference()
    column: Column = FieldColumnReference()

    def __init__(self, bbox: BBox, text: str):
        super().__init__(bbox)
        self.text = text
        self._row = None
        self._column = None

    @staticmethod
    def from_char(char: pd.Series) -> Field:
        return Field(BBox.from_series(char), char.text)

    def add_char(self, char: pd.Series) -> None:
        super().merge(BBox.from_series(char))
        self.text += char.text

    def merge(self, other: Field):
        super().merge(other.bbox)
        self.text += other.text

    def __str__(self) -> str:
        return str(self.text)

    def __repr__(self) -> str:
        return f"'{self.text}'"
