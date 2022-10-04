""" Contains the Field. """

from __future__ import annotations

from datetime import datetime
from typing import Any

from config import Config
from datastructures.pdftable.bbox import BBox, BBoxObject
from datastructures.pdftable.container import (
    Column, FieldColumnReference, FieldRowReference, Row)
from datastructures.pdftable.enums import (
    ColumnType, FieldType, FieldValue, RowType)
from p2g_types import Char


class Field(BBoxObject):
    """ A single field in a PDFTable. """
    row: Row = FieldRowReference()
    column: Column = FieldColumnReference()

    def __init__(self, bbox: BBox, text: str):
        super().__init__(bbox)
        self.text = text.strip()
        self._row = None
        self._column = None

    @property
    def type(self) -> FieldType:
        """ The type of the field. """
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
        """ Creates a new field using a single char. """
        return Field(BBox.from_char(char), char.text)

    def append_char(self, char: Char) -> None:
        """ Add the char to the field. No effort is spent to put the char at
        the correct position (bbox-wise), it is simply appended. """
        super().merge(BBox.from_char(char))
        self.text += char.text

    def merge(self, other: Field):
        """ Merge the two fields, merging their bbox and
        appending other's text to self. """
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

    def fix_name_if_split(self, ref_field: Field) -> bool:
        """ If the name is split wrt. the reference field, add a basename.

        E.g. given a row with stop A with text "Frankfurt - Hauptbahnhof",
         followed by a stop B with text "- Friedhof", then the text of B
         will be changed to "Frankfurt - Friedhof". """
        def get_base_name(ref_text: str) -> str:
            """ Find the most likely base_text ('Frankfurt' in the example)
            of a given text, by splitting the text at common delimiters. """
            split_chars = [",", "-", " "]
            merge_chars = {",": ", ", "-": " - ", " ": " "}
            for split_char in split_chars:
                split_text = ref_text.split(split_char, 1)
                if len(split_text) <= 1:
                    continue
                return split_text[0].strip() + merge_chars[split_char]
            # If we can't determine a base name, the whole name is.
            return ref_text.strip()

        def _starts_with_delim() -> bool:
            for char in ["-", ","]:
                if self.text.startswith(char):
                    return True
            return False

        def _is_indented() -> bool:
            min_indention_in_pts = 3
            dist = abs(ref_field.bbox.x0 - self.bbox.x0)
            return dist >= min_indention_in_pts

        # Order is important, because we want to strip delim even if indented.
        starts_with_delim = _starts_with_delim()
        is_indented = _is_indented()
        if not starts_with_delim and not is_indented:
            return False
        # Same name, but ours is split.
        if ref_field.text.endswith(self.text):
            self.text = ref_field.text
            return True
        text = self.text[1:].strip() if starts_with_delim else self.text
        self.text = get_base_name(ref_field.text) + text
        return True

    def __str__(self) -> str:
        return f"F('{self.text}')"

    def __repr__(self) -> str:
        return f"Field('{self.text}', {self.type}, {self.bbox!r})"
