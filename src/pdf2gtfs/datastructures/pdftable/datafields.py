from __future__ import annotations

from math import copysign
from operator import attrgetter
from typing import (
    Callable, cast, Iterable, NamedTuple, Type, TypeAlias, TypeVar)

from pdfminer.layout import LTChar

from pdf2gtfs.datastructures.pdftable import Char
from pdf2gtfs.datastructures.pdftable.bbox import BBox, BBoxObject


Size: TypeAlias = tuple[int, int]
# TODO NOW: EXPLAAIN
T = TypeVar("T")
B = TypeVar("B", bound="Bounds")
F = TypeVar("F", bound="TableField")
BoundArgs = NamedTuple("BoundArgs", [("func", Callable[[Iterable[F]], F]),
                                     ("bbox_attr", str),
                                     ("return_attr", str)])


class TableField(BBoxObject):
    def __init__(self, chars: list[LTChar], page_height: float) -> None:
        super().__init__(None)
        self.chars = chars
        self.page_height = page_height
        self.set_bbox_from_chars()
        self.owner = None
        self.col = -1
        self.row = -1
        self.text = "".join([c.get_text() for c in self.chars]).strip()

    def set_bbox_from_chars(self) -> None:
        from pdf2gtfs.reader import lt_char_to_dict

        bbox = BBox.from_char(
            Char(**lt_char_to_dict(self.chars[0], self.page_height)))
        self.bbox = bbox
        for ltchar in self.chars:
            char = Char(**lt_char_to_dict(ltchar, self.page_height))
            self.bbox.merge(BBox.from_char(char))

    def to_subtype(self, subtype: Type[T]) -> T:
        return subtype(self.chars, self.page_height)

    def __repr__(self) -> str:
        return (f"{self.__class__.__name__}(row={self.row:>3},"
                f" col={self.col:>3}, text='{self.text}')")


class DataAnnotField(TableField):
    def __init__(self, chars: list[LTChar], page_height: float) -> None:
        super().__init__(chars, page_height)
        self.data_field: DataField | None = None


class DataField(TableField):
    def __init__(self, chars: list[LTChar], page_height: float) -> None:
        super().__init__(chars, page_height)
        self._annotations: list[DataAnnotField] = []

    @property
    def annotations(self) -> list[DataAnnotField]:
        return self._annotations

    @annotations.setter
    def annotations(self, fields: list[DataAnnotField]) -> None:
        for field in fields:
            field.data_field = self
        self._annotations = fields


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
        field_search_delta = int(copysign(1, col_id))
        if col_id < 0:
            col_id = self.grid_size[0] + col_id
        fields = []
        for field_id in range(col_id, len(self.grid), self.grid_size[0]):
            # No row/column can be empty.
            while self.grid[field_id] is None:
                field_id += field_search_delta
            fields.append(self.grid[field_id])
        return fields

    def get_nth_field_of_col(self, row_id: int) -> list[DataField]:
        col_count = self.grid_size[0]
        field_search_delta = int(copysign(col_count, row_id))
        if row_id < 0:
            row_id = self.grid_size[1] + row_id
        fields = []
        start = row_id * col_count
        end = min((len(self.grid), (row_id + 1) * col_count))
        for field_id in range(start, end):
            # No row/column can be empty.
            while self.grid[field_id] is None:
                field_id += field_search_delta
            fields.append(self.grid[field_id])
        return fields

    @staticmethod
    def _grow(bound_cls: Type[B], data_fields: list[DataField],
              fields: list[TableField]) -> list[TableField]:
        # Only grow in a single direction at a time.
        bounds = bound_cls.from_factory_fields(data_fields)
        fields = list(filter(bounds.within_bounds, fields))
        if not fields:
            return fields
        bounds.update_missing_bound(fields)
        fields = list(filter(bounds.within_bounds, fields))
        return fields

    def grow_west(self, fields: list[TableField]) -> list[TableField]:
        data_fields = self.get_nth_field_of_row(0)
        return self._grow(WBounds, data_fields, fields)

    def grow_east(self, fields: list[TableField]) -> list[TableField]:
        data_fields = self.get_nth_field_of_row(-1)
        return self._grow(EBounds, data_fields, fields)

    def grow_north(self, fields: list[TableField]) -> list[TableField]:
        data_fields = self.get_nth_field_of_col(0)
        return self._grow(NBounds, data_fields, fields)

    def grow_south(self, fields: list[TableField]) -> list[TableField]:
        data_fields = self.get_nth_field_of_col(-1)
        return self._grow(SBounds, data_fields, fields)

    def get_contained_fields(self, fields: list[TableField]
                             ) -> list[TableField]:
        bounds = WBounds.from_factory_fields(self.get_nth_field_of_row(0))
        bounds.expand(
            EBounds.from_factory_fields(self.get_nth_field_of_row(-1)))
        bounds.expand(
            NBounds.from_factory_fields(self.get_nth_field_of_col(0)))
        bounds.expand(
            SBounds.from_factory_fields(self.get_nth_field_of_col(-1)))
        print(bounds)
        fields = list(filter(bounds.within_bounds, fields))
        return fields


class Bounds:
    def __init__(self, n: float | None, w: float | None,
                 s: float | None, e: float | None) -> None:
        self._n = n
        self._w = w
        self._s = s
        self._e = e
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

    @property
    def hbox(self) -> BBox | None:
        return self._hbox

    @property
    def vbox(self) -> BBox | None:
        return self._vbox

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

    def expand(self, other: B) -> None:
        """ Update the coordinates to the ones of other if they exist. """
        comp = {"n": "__le__", "s": "__ge__",
                "w": "__le__", "e": "__ge__"}
        for direction in ["n", "w", "s", "e"]:
            new_value = getattr(other, direction)
            if new_value is None:
                continue
            old_value = getattr(self, direction)
            if old_value is not None:
                if getattr(old_value, comp[direction])(new_value):
                    continue
            setattr(self, direction, new_value)

    @staticmethod
    def get_bound_from_fields(args: BoundArgs | None, fields: list[TableField]
                              ) -> float | None:
        if args is None:
            return None
        func, bbox_coordinate, return_coordinate = args
        field = func(fields, key=attrgetter(f"bbox.{bbox_coordinate}"))
        return cast(float, attrgetter(f"bbox.{return_coordinate}")(field))

    @classmethod
    def from_factory_fields(cls, fields: list[DataField], **kwargs) -> B:
        bounds = {d: cls.get_bound_from_fields(kwargs.get(d), fields)
                  for d in ["n", "w", "s", "e"]}
        return cls(**bounds)

    def _update_single_bound(
            self, which: str, args: BoundArgs, fields: list[TableField]
            ) -> None:
        """ Update a single bound using the BoundArgs and the fields.

        which can be one of "n", "w", "s", "e".
        """
        setattr(self, which, self.get_bound_from_fields(args, fields))

    def __repr__(self) -> str:
        cls_name = self.__class__.__name__
        fmt = "{:>7.2f}"
        n = fmt.format(self.n) if self.n is not None else "None"
        w = fmt.format(self.w) if self.w is not None else "None"
        s = fmt.format(self.s) if self.s is not None else "None"
        e = fmt.format(self.e) if self.e is not None else "None"
        return f"{cls_name}(n={n}, w={w}, s={s}, e={e})"


class WBounds(Bounds):
    @classmethod
    def from_factory_fields(cls, fields: list[DataField], **_) -> WBounds:
        kwargs = {"n": BoundArgs(min, "y0", "y0"),
                  "s": BoundArgs(max, "y1", "y1"),
                  "e": BoundArgs(min, "x0", "x0")}
        return super().from_factory_fields(fields, **kwargs)

    def update_missing_bound(self, fields: list[TableField]) -> None:
        """
        Update the western bound, which was not created using the datafields.
        """
        args: BoundArgs = BoundArgs(max, "x0", "x0")
        self._update_single_bound("w", args, fields)


class EBounds(Bounds):
    @classmethod
    def from_factory_fields(cls, fields: list[DataField], **_) -> EBounds:
        kwargs = {"n": BoundArgs(min, "y0", "y0"),
                  "s": BoundArgs(max, "y1", "y1"),
                  "w": BoundArgs(max, "x1", "x1")}
        return super().from_factory_fields(fields, **kwargs)

    def update_missing_bound(self, fields: list[TableField]) -> None:
        """
        Update the eastern bound, which was not created using the datafields.
        """
        args: BoundArgs = BoundArgs(min, "x1", "x1")
        self._update_single_bound("e", args, fields)


class NBounds(Bounds):
    @classmethod
    def from_factory_fields(cls, fields: list[DataField], **_) -> NBounds:
        kwargs = {"w": BoundArgs(min, "x0", "x0"),
                  "s": BoundArgs(min, "y0", "y0"),
                  "e": BoundArgs(max, "x1", "x1")}
        return super().from_factory_fields(fields, **kwargs)

    def update_missing_bound(self, fields: list[TableField]) -> None:
        """
        Update the eastern bound, which was not created using the datafields.
        """
        args: BoundArgs = BoundArgs(max, "y0", "y0")
        self._update_single_bound("n", args, fields)


class SBounds(Bounds):
    @classmethod
    def from_factory_fields(cls, fields: list[DataField], **_) -> SBounds:
        kwargs = {"n": BoundArgs(max, "y1", "y1"),
                  "w": BoundArgs(min, "x0", "x0"),
                  "e": BoundArgs(max, "x1", "x1")}
        return super().from_factory_fields(fields, **kwargs)

    def update_missing_bound(self, fields: list[TableField]) -> None:
        """
        Update the eastern bound, which was not created using the datafields.
        """
        args: BoundArgs = BoundArgs(min, "y1", "y1")
        self._update_single_bound("s", args, fields)
