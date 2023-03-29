from __future__ import annotations

from operator import attrgetter
from typing import TypeAlias

from pdfminer.layout import LTChar

from pdf2gtfs.datastructures.pdftable import Char
from pdf2gtfs.datastructures.pdftable.bbox import BBox, BBoxObject


Size: TypeAlias = tuple[int, int]


class DataField(BBoxObject):
    def __init__(self, chars: list[LTChar], page_height: float) -> None:
        super().__init__(None)
        self.chars = chars
        self.set_bbox_from_chars(page_height)
        self.datafields = None
        self.col = -1
        self.row = -1
        self.text = "".join([c.get_text() for c in self.chars])

    def set_bbox_from_chars(self, page_height: float) -> None:
        from pdf2gtfs.reader import lt_char_to_dict
        bbox = BBox.from_char(
            Char(**lt_char_to_dict(self.chars[0], page_height)))
        self.bbox = bbox
        for ltchar in self.chars:
            char = Char(**lt_char_to_dict(ltchar, page_height))
            self.bbox.merge(BBox.from_char(char))

    def _overlap(self, other: DataField, d: str) -> float:
        """ Return how much self and other overlap, in pixel. """
        # TODO NOW: Move to BBox.
        # TODO: Check if this is actually pixel.
        assert d in ["x", "y"]
        # Sort the two objects by the left/upper side, to have fewer cases.
        one, two = sorted((self, other), key=attrgetter(f"bbox.{d}0"))

        # The left/top of the righter/lower object is greater than the
        #  right/bottom of the lefter/upper object.
        if getattr(one.bbox, f"{d}1") <= getattr(two.bbox, f"{d}0"):
            return 0
        # The righer/lower object is completely contained in the lefter/upper.
        if getattr(one.bbox, f"{d}1") >= getattr(two.bbox, f"{d}1"):
            return two.bbox.size[0] if d == "x" else two.bbox.size[1]
        # Need to actually calculate the overlap.
        return abs(getattr(one.bbox, f"{d}1") - getattr(two.bbox, f"{d}0"))

    def v_overlap(self, other: DataField) -> float:
        """ Return how much self and other overlap vertically, in pixel. """
        return self._overlap(other, "x")

    def h_overlap(self, other: DataField) -> float:
        """ Return how much self and other overlap horizontally, in pixel. """
        return self._overlap(other, "y")

    def is_v_overlap(self, other: DataField) -> bool:
        return self.v_overlap(other) >= 0.5 * self.bbox.size[0]

    def is_h_overlap(self, other: DataField) -> bool:
        return self.h_overlap(other) >= 0.5 * self.bbox.size[1]

    def __repr__(self) -> str:
        return (f"DataField(row={self.row:>3},"
                f" col={self.col:>3}, text='{self.text}')")


class DataFields:
    def __init__(self) -> None:
        self.grid: list[DataField] = []
        self._grid_size: Size = 0, 0

    @property
    def grid_size(self) -> Size:
        """ Width/Height of the grid. """
        return self._grid_size

    def set_grid_from_fields(
            self, fields: list[DataField], size: Size) -> None:
        """ Creates a full grid, where positions without a field are None. """
        fields = sorted(fields, key=attrgetter("row", "col"))
        prev = fields[0]
        grid = [prev]
        for field in fields[1:]:
            new_line = field.row == prev.row + 1
            count = field.col - (prev.col + 1)
            if new_line:
                count = field.col
                # Previous field was not in the last column.
                if prev.col + 1 < size[0]:
                    count += size[0] - 1 - prev.col
            for _ in range(count):
                grid.append(None)
            grid.append(field)
            prev = field
        while len(grid) < size[0] * size[1]:
            grid.append(None)

        self.grid = grid

    def update_fields(self, fields: list[DataField]) -> Size:
        """ Sets the datafields, row and column of each field. """
        # Set the column id of the fields
        fields = sorted(fields, key=attrgetter("bbox.x0", "bbox.y0"))
        column_starter = fields[0]
        col = 0
        for field in fields:
            if not column_starter.is_v_overlap(field):
                column_starter = field
                col += 1
            field.datafields = self
            field.col = col
        # Set the row id of the fields.
        row = 0
        fields = sorted(fields, key=attrgetter("bbox.y0", "bbox.x0"))
        row_starter = fields[0]
        for field in fields:
            if not row_starter.is_h_overlap(field):
                row_starter = field
                row += 1
            field.row = row
        return col + 1, row + 1

    @staticmethod
    def from_list(fields: list[DataField]) -> DataFields:
        datafields = DataFields()
        size = datafields.update_fields(fields)
        datafields._grid_size = size
        datafields.set_grid_from_fields(fields, size)
        return datafields

    def print_as_table(self) -> None:
        msg = ""
        for row_id in range(self.grid_size[1]):
            msg += "\n"
            for col_id in range(self.grid_size[0]):
                field = self.grid[col_id + self.grid_size[0] * row_id]
                msg += "|"
                msg += f"{field.text: >5}" if field else "     "
                msg += "|"
        print(msg)
