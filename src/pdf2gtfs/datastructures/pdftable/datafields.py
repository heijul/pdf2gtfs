from __future__ import annotations

from functools import partial
from operator import attrgetter
from typing import Callable, TypeAlias

from pdfminer.layout import LTChar

from pdf2gtfs.datastructures.pdftable import Char
from pdf2gtfs.datastructures.pdftable.bbox import BBox, BBoxObject


Size: TypeAlias = tuple[int, int]


class TableField(BBoxObject):
    def __init__(self, chars: list[LTChar], page_height: float) -> None:
        super().__init__(None)
        self.chars = chars
        self.set_bbox_from_chars(page_height)
        self.owner = None
        self.col = -1
        self.row = -1
        self.text = "".join([c.get_text() for c in self.chars]).strip()

    def set_bbox_from_chars(self, page_height: float) -> None:
        from pdf2gtfs.reader import lt_char_to_dict
        bbox = BBox.from_char(
            Char(**lt_char_to_dict(self.chars[0], page_height)))
        self.bbox = bbox
        for ltchar in self.chars:
            char = Char(**lt_char_to_dict(ltchar, page_height))
            self.bbox.merge(BBox.from_char(char))

    def __repr__(self) -> str:
        return (f"{self.__class__.__name__}(row={self.row:>3},"
                f" col={self.col:>3}, text='{self.text}')")


class DataField(TableField):
    pass


class TableFactory:
    def __init__(self) -> None:
        self.grid: list[DataField] = []
        self._grid_size: Size = 0, 0

    @property
    def grid_size(self) -> Size:
        """ Width/Height of the grid in number of fields. """
        return self._grid_size

    def set_grid_from_datafields(
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

    def update_data_fields(self, fields: list[DataField]) -> Size:
        """ Sets the owner, row and column of each field. """
        # Set the column id of the fields
        fields = sorted(fields, key=attrgetter("bbox.x0", "bbox.y0"))
        column_starter = fields[0]
        col = 0
        for field in fields:
            if not column_starter.bbox.is_h_overlap(field.bbox):
                column_starter = field
                col += 1
            field.owner = self
            field.col = col
        # Set the row id of the fields.
        row = 0
        fields = sorted(fields, key=attrgetter("bbox.y0", "bbox.x0"))
        row_starter = fields[0]
        for field in fields:
            if not row_starter.bbox.is_v_overlap(field.bbox):
                row_starter = field
                row += 1
            field.row = row
        return col + 1, row + 1

    @staticmethod
    def from_datafields(fields: list[DataField]) -> TableFactory:
        factory = TableFactory()
        size = factory.update_data_fields(fields)
        factory._grid_size = size
        factory.set_grid_from_datafields(fields, size)
        return factory

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

    def get_column(self, col_id: int) -> list[DataField]:
        return list(filter(None, self.grid[col_id::self.grid_size[0]]))

    def get_nth_field_of_row(self, col_id: int) -> list[DataField]:
        fields = []
        for field_id in range(col_id, len(self.grid), self.grid_size[0]):
            # No row/column can be empty.
            while self.grid[field_id] is None:
                field_id += 1
            fields.append(self.grid[field_id])
        return fields

    def grow_west(self, fields: list[TableField]) -> None:
        # Only grow in a single direction at a time.
        first_fields = self.get_nth_field_of_row(0)
        bounds = get_west_bounds(first_fields, "w", "e")
        fields = list(filter(bounds.within_bounds, fields))
        bounds.w = get_west_bounds(fields, "nse", "w").w
        fields = list(filter(bounds.within_bounds, fields))
        return fields


def _get_bounds(attrs: dict, fields: list[TableField],
                ignore: str = "", use_inner: str = "") -> Bounds:
    """ Returns the bounds for the cardinal directions.

    Both ignore and use_inner should be a string containing one or multiple
    of "n", "w", "s" and "e".
    For ignore, the bounds will only be calculated for those directions not
    specified.
    For use_inner, when a direction is specified, it will use the inner bound,
    i.e. the # TODO NOW:
    """
    # Only one coordinate can be the inner one in a single direction.
    # TODO: Could allow this and swap or no swap?
    assert (not ("n" in use_inner and "s" in use_inner) and
            not ("w" in use_inner and "e" in use_inner))
    # Remove ignored directions.
    attrs = {key: value for key, value in attrs.items() if key not in ignore}
    # Swap func, if we are looking for the inner bound instead of the outer.
    func_conversion = {min: max, max: min}
    for inner in use_inner:
        func = attrs[inner][0]
        attrs[inner] = (func_conversion[func], attrs[inner][1])

    return Bounds({key: func(fields, key=attrgetter(f"bbox.{attr}")).bbox
                   for key, (func, attr) in attrs.items()})


def get_west_bounds(fields: list[TableField], ignore: str = "",
                    use_inner: str = "") -> Bounds:
    outer_attrs = {"n": (min, "y0"), "w": (min, "x0"),
                   "s": (max, "y1"), "e": (max, "x0")}
    return _get_bounds(outer_attrs, fields, ignore, use_inner)


def get_east_bounds(fields: list[TableField], ignore: str = "",
                    use_inner: str = "") -> Bounds:
    outer_attrs = {"n": (min, "y0"), "w": (min, "x1"),
                   "s": (max, "y1"), "e": (max, "x1")}
    return _get_bounds(outer_attrs, fields, ignore, use_inner)


def _filter_within_bounds(bounds: dict[str: TableField], field: TableField
                          ) -> bool:
    return ((not bounds.get("n") or field.bbox.y0 >= bounds["n"].bbox.y0) and
            (not bounds.get("s") or field.bbox.y1 <= bounds["s"].bbox.y1) and
            (not bounds.get("w") or field.bbox.x0 >= bounds["w"].bbox.x0) and
            (not bounds.get("e") or field.bbox.x1 <= bounds["e"].bbox.x1))


def filter_within_bounds(
        bounds: dict[str: TableField]) -> Callable[[TableField], bool]:
    """ Return a function, that can be used with filter() on a TableField list.

    The returned function will return True iff the given TableField is within
    the bounds. If a bound was not given, only the others are evaluated.
    """
    return partial(_filter_within_bounds, bounds)

    return (
        lambda field:
        (not bounds.get("n") or field.bbox.y0 >= bounds["n"].bbox.y0) and
        (not bounds.get("s") or field.bbox.y1 <= bounds["s"].bbox.y1) and
        (not bounds.get("w") or field.bbox.x0 >= bounds["w"].bbox.x0) and
        (not bounds.get("e") or field.bbox.x1 <= bounds["e"].bbox.x1))


class Bounds:
    def __init__(self, bounds: dict[str: BBox]) -> None:
        self._n = bounds["n"].y0 if "n" in bounds and bounds["n"] else None
        self._w = bounds["w"].x0 if "w" in bounds and bounds["w"] else None
        self._s = bounds["s"].y1 if "s" in bounds and bounds["s"] else None
        self._e = bounds["e"].x0 if "e" in bounds and bounds["e"] else None
        self._update_hbox()
        self._update_vbox()

    @property
    def n(self) -> float | None:
        return self._n

    @n.setter
    def n(self, value: float | None) -> None:
        self._n = value
        self._update_vbox()

    @property
    def s(self) -> float | None:
        return self._s

    @s.setter
    def s(self, value: float | None) -> None:
        self._s = value
        self._update_vbox()

    @property
    def w(self) -> float | None:
        return self._w

    @w.setter
    def w(self, value: float | None) -> None:
        self._w = value
        self._update_hbox()

    @property
    def e(self) -> float | None:
        return self._e

    @e.setter
    def e(self, value: float | None) -> None:
        self._e = value
        self._update_hbox()

    def _update_hbox(self) -> None:
        if self.w is None or self.e is None:
            hbox = None
        else:
            hbox = BBox(self.w, -1, self.e, -1)
        self._hbox = hbox

    def _update_vbox(self) -> None:
        if self.n is None or self.s is None:
            vbox = None
        else:
            vbox = BBox(-1, self.n, -1, self.s)
        self._vbox = vbox

    @property
    def hbox(self) -> BBox | None:
        return self._hbox

    @property
    def vbox(self) -> BBox | None:
        return self._vbox

    def _within_h_bounds(self, bbox: BBox) -> bool:
        if self.hbox and self.hbox.is_h_overlap(bbox):
            return True
        if self.hbox:
            return False
        if self.w is not None and bbox.x1 <= self.w:
            return False
        if self.e is not None and bbox.x0 >= self.e:
            return False
        return True

    def _within_v_bounds(self, bbox: BBox) -> bool:
        if self.vbox and self.vbox.is_v_overlap(bbox):
            return True
        if self.vbox:
            return False
        if self.n is not None and bbox.y1 <= self.n:
            return False
        if self.s is not None and bbox.y0 >= self.s:
            return False
        return True

    def within_bounds(self, obj: TableField) -> bool:
        bbox = obj.bbox
        return self._within_h_bounds(bbox) and self._within_v_bounds(bbox)
