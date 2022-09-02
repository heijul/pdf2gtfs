from __future__ import annotations

from datastructures.rawtable.bbox import BBox, BBoxObject
from datastructures.rawtable.container import (
    Column, FieldColumnReference, FieldRowReference, Row)
from p2g_types import Char


class Field(BBoxObject):
    row: Row = FieldRowReference()
    column: Column = FieldColumnReference()

    def __init__(self, bbox: BBox, text: str):
        super().__init__(bbox)
        self.text = text
        self._row = None
        self._column = None

    @staticmethod
    def from_char(char: Char) -> Field:
        return Field(BBox.from_char(char), char.text)

    def add_char(self, char: Char) -> None:
        super().merge(BBox.from_char(char))
        self.text += char.text

    def merge(self, other: Field):
        super().merge(other)
        self.text += other.text

    def __str__(self) -> str:
        return str(self.text)

    def __repr__(self) -> str:
        return f"Field('{self.text}')"
