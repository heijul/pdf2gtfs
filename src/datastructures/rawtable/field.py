from __future__ import annotations

from datetime import datetime
from typing import Any

from config import Config
from datastructures.rawtable.bbox import BBox, BBoxObject
from datastructures.rawtable.container import (
    Column, FieldColumnReference, FieldRowReference, Row)
from datastructures.rawtable.enums import (
    ColumnType, FieldType, FieldValue, RowType)
from p2g_types import Char


class Field(BBoxObject):
    row: Row = FieldRowReference()
    column: Column = FieldColumnReference()

    def __init__(self, bbox: BBox, text: str):
        super().__init__(bbox)
        self.text = text
        self._row = None
        self._column = None

    @property
    def type(self) -> FieldType:
        # Can not check for type directly as that may try to update it first.
        has_stop_column = (self.column and self.column.has_type()
                           and self.column.type == ColumnType.STOP)
        has_data_row = (self.row and self.row.has_type() and
                        self.row.type == RowType.DATA)
        if has_stop_column and has_data_row:
            return FieldType.STOP

        if FieldValue.HEADER in self:
            return FieldType.HEADER
        if FieldValue.REPEAT in self:
            return FieldType.REPEAT
        if FieldValue.TIME_DATA in self:
            return FieldType.DATA
        if FieldValue.STOP_ANNOT in self:
            return FieldType.STOP_ANNOT
        if FieldValue.ROW_ANNOT in self:
            return FieldType.ROW_ANNOT
        if FieldValue.ROUTE_INFO in self:
            return FieldType.ROUTE_INFO
        return FieldType.OTHER

    @staticmethod
    def from_char(char: Char) -> Field:
        return Field(BBox.from_char(char), char.text)

    def add_char(self, char: Char) -> None:
        super().merge(BBox.from_char(char))
        self.text += char.text

    def merge(self, other: Field):
        super().merge(other)
        self.text += other.text

    def _contains_time_data(self) -> bool:
        try:
            datetime.strptime(self.text, Config.time_format)
            return True
        except ValueError:
            return False

    def _contains(self, idents: list[str], strict: bool = True) -> bool:
        def _contains_single(ident: str) -> bool:
            ident = ident.lower().strip()
            if strict:
                return ident == text
            return ident in text

        text = self.text.lower().strip()
        return any(map(_contains_single, idents))

    def __contains__(self, item: Any) -> bool:
        if not isinstance(item, FieldValue):
            return False
        if item == FieldValue.TIME_DATA:
            return self._contains_time_data()
        if item == FieldValue.HEADER:
            return self._contains(Config.header_values)
        if item == FieldValue.ROUTE_INFO:
            return self._contains(Config.route_identifier)
        if item == FieldValue.REPEAT:
            return any(map(self._contains, Config.repeat_identifier))
        if item == FieldValue.ROW_ANNOT:
            return self._contains(Config.annot_identifier)
        if item == FieldValue.STOP_ANNOT:
            return (self._contains(Config.arrival_identifier) or
                    self._contains(Config.departure_identifier))

    # TODO: Improve str/repr
    def __str__(self) -> str:
        return str(self.text)

    def __repr__(self) -> str:
        return f"Field('{self.text}')"
