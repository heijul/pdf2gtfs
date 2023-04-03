from __future__ import annotations

from math import copysign
from operator import attrgetter
from typing import Callable, cast, Iterable, NamedTuple, Type, TypeVar

from pdfminer.layout import LTChar

from pdf2gtfs.datastructures.pdftable import Char
from pdf2gtfs.datastructures.pdftable.bbox import BBox, BBoxObject


# TODO NOW: EXPLAAIN THESE
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
        # TODO NOW: Move to _initialize; Check if chars are same font/fontsize.
        self.font = self.chars[0].font if self.chars else None
        self.fontsize = self.chars[0].fontsize if self.chars else None
        self.page_height = page_height
        self.owner = None
        self._next = None
        self._prev = None
        self._above = None
        self._below = None
        self._initialize()

    def _initialize(self) -> None:
        self.set_bbox_from_chars()
        self.text = "".join([c.get_text() for c in self.chars]).strip()

    def _set_neighbor(self, attr: str, ref_attr: str,
                      field: TableField | None) -> None:
        """ Ensure the neighbor is symmetric. """
        assert self != field
        assert attr.startswith("_") and not ref_attr.startswith("_")
        setattr(self, attr, field)
        if field is None or getattr(field, ref_attr) == self:
            return
        setattr(field, ref_attr, self)

    @property
    def next(self) -> TableField:
        return self._next

    @next.setter
    def next(self, field: TableField | None) -> None:
        self._set_neighbor("_next", "prev", field)

    @property
    def prev(self) -> TableField | None:
        return self._prev

    @prev.setter
    def prev(self, field: TableField | None) -> None:
        self._set_neighbor("_prev", "next", field)

    @property
    def above(self) -> TableField | None:
        return self._above

    @above.setter
    def above(self, field) -> None:
        self._set_neighbor("_above", "below", field)

    @property
    def below(self) -> TableField | None:
        return self._below

    @below.setter
    def below(self, field: TableField | None) -> None:
        self._set_neighbor("_below", "above", field)

    def set_bbox_from_chars(self) -> None:
        from pdf2gtfs.reader import lt_char_to_dict

        if not self.chars:
            return

        bbox = BBox.from_char(
            Char(**lt_char_to_dict(self.chars[0], self.page_height)))
        self.bbox = bbox
        for ltchar in self.chars:
            char = Char(**lt_char_to_dict(ltchar, self.page_height))
            self.bbox.merge(BBox.from_char(char))

    def to_subtype(self, subtype: Type[T]) -> T:
        return subtype(self.chars, self.page_height)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(text='{self.text}')"


class EmptyTableField(TableField):
    def __init__(self, **kwargs) -> None:
        # An empty field can never contain any characters.
        kwargs.update(dict(chars=[], page_height=0))
        super().__init__(**kwargs)

    def _initialize(self) -> None:
        self.text = ""


class DataAnnotField(TableField):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.data_field: DataField | None = None


class DataField(TableField):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._annotations: list[DataAnnotField] = []
        self.col = -1
        self.row = -1

    @property
    def annotations(self) -> list[DataAnnotField]:
        return self._annotations

    @annotations.setter
    def annotations(self, fields: list[DataAnnotField]) -> None:
        for field in fields:
            field.data_field = self
        self._annotations = fields

    def __repr__(self) -> str:
        if not hasattr(self, "row") or not hasattr(self, "col"):
            return super().__repr__()
        return (f"{self.__class__.__name__}(row={self.row:>3},"
                f" col={self.col:>3}, text='{self.text}')")


class EmptyDataField(EmptyTableField, DataField):
    def __init__(self, row: int, col: int, **kwargs) -> None:
        super().__init__(**kwargs)
        # This will fail (as it should), when only one of row/col is provided.
        if row >= 0 or col >= 0:
            self.row = row
            self.col = col


class TableFactory:
    def __init__(self) -> None:
        self.first: TableField | None = None
        self.last: TableField | None = None
        self._col_count = 0
        self._row_count = 0

    @property
    def row_count(self) -> int:
        """ Number of fields in each column. """
        return self._row_count

    @property
    def col_count(self) -> int:
        """ Number of fields in each row. """
        return self._col_count

    def set_datafield_positions(self, fields: list[DataField]) -> None:
        """ Sets the owner, row and column of each datafield. """
        # Get the columns, based on how much a field overlaps horizontally
        # with the first (= left-most) field of each column.
        fields = sorted(fields, key=attrgetter("bbox.x0", "bbox.y0"))
        column_starter = fields[0]
        col = 0
        for field in fields:
            # If a field does not overlap horizontally, start a new column.
            if not column_starter.bbox.is_h_overlap(field.bbox):
                column_starter = field
                col += 1
            field.owner = self
            field.col = col
        self._col_count = col + 1
        # Get the rows, based on how much a field overlaps vertically
        # with the first (= highest) field in each row.
        row = 0
        fields = sorted(fields, key=attrgetter("bbox.y0", "bbox.x0"))
        row_starter = fields[0]
        for field in fields:
            # If a field does not overlap vertically, start a new row.
            if not row_starter.bbox.is_v_overlap(field.bbox):
                row_starter = field
                row += 1
            field.row = row
        self._row_count = row + 1

    def create_grid_from_datafield(self, fields: list[DataField]
                                   ) -> list[DataField]:
        """ Creates a full grid, where positions without a field are None. """
        fields = sorted(fields, key=attrgetter("row", "col"))
        prev = fields[0]
        grid = [prev]
        for field in fields[1:]:
            new_line = field.row > prev.row
            # Fill empty fields at the end of the previous row.
            if new_line:
                for col in range(prev.col + 1, self.col_count):
                    grid.append(EmptyDataField(prev.row, col))
            # Fill empty fields between previous field/start of row and field.
            start = 0 if new_line else prev.col + 1
            end = field.col
            for col in range(start, end):
                grid.append(EmptyDataField(field.row, col))
            grid.append(field)
            prev = field
        # Add emtpy fields at the end, in case the last row is not full.
        last_field = grid[-1]
        for col in range(last_field.col + 1, self.col_count):
            grid.append(EmptyDataField(last_field.row, col))
        return grid

    def link_datafields(self, grid: list[DataField]) -> None:
        """ Link each field to each of its neighbors. """
        prev = None
        for i, field in enumerate(grid):
            if not self.first:
                self.first = field
            if i >= self.col_count:
                pos = field.row * self.col_count + field.col
                field.above = grid[pos - self.col_count]
            # field.prev/.next are always on the same line.
            new_line = i % self.col_count == 0
            if not new_line and prev is not None:
                prev.next = field
            prev = field
            self.last = field
            # These are only required for grid creation.
            del field.row
            del field.col

    @staticmethod
    def from_datafields(fields: list[DataField]) -> TableFactory:
        factory = TableFactory()
        factory.set_datafield_positions(fields)
        factory.link_datafields(factory.create_grid_from_datafield(fields))
        return factory

    def print_fields(self, max_field_length: int = 5,
                     max_line_length: int = 180) -> None:
        def lin_len(field: TableField) -> int:
            return max([len(f.text[:max_field_length])
                        for f in self.get_fields_in("v", field)]) + 1

        def orient(f: TableField) -> str:
            if isinstance(f, DataField):
                return ">"
            return "<"

        col = self.get_fields_in("v", self.first)
        rows = [self.get_fields_in("h", field) for field in col]
        delim = " | "
        lines = [delim.join(
            [f"{f.text[:max_field_length]: {orient(f)}{lin_len(f)}}"
             for f in row]) for row in rows]
        msg = f"{delim.rstrip()}\n{delim.lstrip()}".join(
            [line[:max_line_length] for line in lines])
        msg = f"{delim.lstrip()}{msg}{delim.rstrip()}"
        print(msg)

    @staticmethod
    def get_row_or_column_of_field(lower_attr: str, upper_attr: str,
                                   field: TableField) -> list[TableField]:
        """ Return all fields of the row/column of field. """
        # Move all the way left/up.
        while getattr(field, lower_attr):
            field = getattr(field, lower_attr)
        # Add all fields in the linked list up to the end of the row/column.
        fields = []
        while field:
            fields.append(field)
            field = getattr(field, upper_attr)
        return fields

    def replace(self, old_field: TableField, new_field: TableField) -> None:
        new_field.next = old_field.next
        new_field.prev = old_field.prev
        new_field.above = old_field.above
        new_field.below = old_field.below
        if old_field == self.first:
            self.first = new_field
        if old_field == self.last:
            self.last = new_field

    def get_fields_in(self, orientation: str, field: F) -> list[F]:
        """ Return the row or column of field, based on orientation. """
        assert orientation in ["v", "h", "below", "above", "next", "prev"]

        if orientation in ["h", "next", "prev"]:
            return self.get_row_or_column_of_field("prev", "next", field)
        return self.get_row_or_column_of_field("above", "below", field)

    def get_nonempty_fields(self, existing_field: F,
                            search_direction: str) -> list[F]:
        """ Return the first nonempty fields in the row/col of field,
        in the given direction. """
        # We need to have a column to search horizontally and a row
        # to search vertically or non-empty fields.
        fields = []
        for field in self.get_fields_in("v", existing_field):
            # We are looking for non-empty fields.
            while field and isinstance(field, EmptyTableField):
                field = getattr(field, search_direction)
            # Reached end of row/column.
            if field is None:
                continue
            fields.append(field)
        return fields

    def get_nth_field_of_row(self, col_id: int) -> list[DataField]:
        field_search_delta = int(copysign(1, col_id))
        if col_id < 0:
            col_id = self.col_count + col_id
        fields = []
        for field_id in range(col_id, len(self.grid), self.col_count):
            # No row/column can be empty.
            while self.grid[field_id] is None:
                field_id += field_search_delta
            fields.append(self.grid[field_id])
        return fields

    def get_nth_field_of_col(self, row_id: int) -> list[DataField]:
        field_search_delta = int(copysign(self.col_count, row_id))
        if row_id < 0:
            row_id = self.row_count + row_id
        fields = []
        start = row_id * self.col_count
        end = min((len(self.grid), (row_id + 1) * self.col_count))
        for field_id in range(start, end):
            # No row/column can be empty.
            while self.grid[field_id] is None:
                field_id += field_search_delta
            fields.append(self.grid[field_id])
        return fields

    @staticmethod
    def _grow(bound_cls: Type[B], factory_fields: list[TableField],
              fields: list[TableField]) -> list[TableField]:
        # Only grow in a single direction at a time.
        bounds = bound_cls.from_factory_fields(factory_fields)
        fields = list(filter(bounds.within_bounds, fields))
        if not fields:
            return fields
        bounds.update_missing_bound(fields)
        # These are the fields that fit all bounds.
        minimal_fields = list(filter(bounds.within_bounds, fields))
        # Also try to add fields, that fit only three bounds, but are
        # overlapping with fields, that fit all four.
        overlap_func = ("is_h_overlap" if bound_cls in [WBounds, EBounds]
                        else "is_v_overlap")
        within_bounds_fields = []
        for field in fields:
            for min_field in minimal_fields:
                if getattr(field.bbox, overlap_func)(min_field.bbox, 0.8):
                    within_bounds_fields.append(field)
                    break
        return within_bounds_fields

    @staticmethod
    def add_new_fields(new_fields: list[F], num: int,
                       check_overlap: Callable[[int, F], bool],
                       insert_between_existing: Callable[[int, F], bool],
                       ) -> None:
        new_fields.sort(reverse=True, key=attrgetter("bbox.y0", "bbox.x0"))
        new_field = new_fields.pop()

        i = 0
        while i < num:
            if not new_field:
                break
            if check_overlap(i, new_field):
                new_field = new_fields.pop() if new_fields else None
                continue
            if insert_between_existing(i, new_field):
                new_field = new_fields.pop() if new_fields else None
                # If we inserted a new row/col, we need to check overlap again.
                continue
            i += 1

    def add_new_fields_horizontal(self, start: F, fields: list[F]) -> None:
        """ Adds a new column, based on start and adds the fields.

        For this, we add an empty column, which is updated using the fields.
        """
        def check_overlap(i: int, field: F) -> bool:
            """ Check if the field overlaps vertically, with the first non-
            empty field at i and replace the corresponding border field. """
            if field and non_empty[i].bbox.is_v_overlap(field.bbox):
                self.replace(border_fields[i], field)
                return True
            return False

        def insert_between_existing(i: int, field: F) -> bool:
            """ Inserts a new, empty row for the field, if necessary. """
            if not field or non_empty[i].bbox.y0 + offset < field.bbox.y0:
                return False
            self.insert_row("above", border_fields[i])
            self.replace(border_fields[i].above, field)
            return True

        assert start in (self.first, self.last)
        offset = 0.5
        if start == self.first:
            args = ("next", "prev", "first")
        else:
            args = ("prev", "next", "last")

        non_empty = self.get_nonempty_fields(start, args[0])
        self.insert_col(args[1], start)
        border_fields = self.get_fields_in("v", getattr(self, args[2]))

        assert all((isinstance(f, EmptyTableField) for f in border_fields))
        self.add_new_fields(
            fields, self.row_count, check_overlap, insert_between_existing)

    def add_new_fields_vertical(self, start: F, fields: list[F]) -> None:
        def check_overlap(i: int, field: F) -> bool:
            """ Check if the field overlaps horizontally, with the first non-
            empty field at i and replace the corresponding border field. """
            if field and non_empty[i].bbox.is_h_overlap(field.bbox):
                self.replace(border_fields[i], field)
                return True
            return False

        def insert_between_existing(i: int, field: F) -> bool:
            """ Inserts a new, empty column for the field, if necessary. """
            if not field or non_empty[i].bbox.x0 + offset < field.bbox.x0:
                return False
            self.insert_col("prev", border_fields[i])
            self.replace(border_fields[i].prev, field)
            return True

        assert start in (self.first, self.last)
        offset = 0.5
        if start == self.first:
            args = ("below", "above", "first")
        else:
            args = ("above", "below", "last")

        non_empty = self.get_nonempty_fields(start, args[0])
        self.insert_row(args[1], start)
        border_fields = self.get_fields_in("h", getattr(self, args[2]))

        assert all((isinstance(f, EmptyTableField) for f in border_fields))
        self.add_new_fields(
            fields, self.col_count, check_overlap, insert_between_existing)

    def try_add_fields(self, bounds_cls: Type[B], start: F, fields: list[F],
                       search_dir: str, add_func: Callable[[F, list[F]], None]
                       ) -> bool:
        data_fields = self.get_nonempty_fields(start, search_dir)
        new_fields = self._grow(bounds_cls, data_fields, fields)
        if not new_fields:
            return False

        add_func(start, new_fields)
        # Remove newly added fields.
        for field in new_fields:
            fields.remove(field)
        return True

    def grow_west(self, fields: list[TableField]) -> bool:
        """ Tries to insert the fields, if they are left of the table. """
        return self.try_add_fields(WBounds, self.first, fields, "next",
                                   self.add_new_fields_horizontal)

    def grow_east(self, fields: list[TableField]) -> bool:
        """ Tries to insert the fields, if they are right of the table. """
        return self.try_add_fields(EBounds, self.last, fields, "prev",
                                   self.add_new_fields_horizontal)

    def grow_north(self, fields: list[TableField]) -> bool:
        """ Tries to insert the fields, if they are above the table. """
        return self.try_add_fields(NBounds, self.first, fields, "below",
                                   self.add_new_fields_vertical)

    def grow_south(self, fields: list[TableField]) -> bool:
        """ Tries to insert the fields, if they are below the table. """
        return self.try_add_fields(SBounds, self.last, fields, "above",
                                   self.add_new_fields_vertical)

    @staticmethod
    def link_fields(attr: str, fields: list[F]) -> None:
        """ Link the fields in the list, such that f[i].attr = f[i + 1]. """
        prev = fields[0]
        for field in fields[1:]:
            setattr(field, attr, prev)
            prev = field

    def create_empty_row(self) -> list[EmptyTableField]:
        """ Creates a row containing only empty fields. """
        row = [EmptyTableField() for _ in range(self.col_count)]
        self.link_fields("prev", row)
        return row

    def create_empty_col(self) -> list[EmptyTableField]:
        """ Creates a column containing only empty fields. """
        col = [EmptyTableField() for _ in range(self.row_count)]
        self.link_fields("above", col)
        return col

    def _insert(self, attr: str, existing: list[F], new: list[F]) -> None:
        """ Insert the new fields adjacent (defined by attr), to existing. """
        assert attr in ["above", "below", "next", "prev"]

        for exist_field, new_field in zip(existing, new, strict=True):
            setattr(new_field, attr, getattr(exist_field, attr))
            setattr(exist_field, attr, new_field)
        # Update the first/last field of the table, if necessary.
        if attr in ["above", "prev"] and getattr(self.first, attr):
            self.first = getattr(self.first, attr)
        if attr in ["below", "next"] and getattr(self.last, attr):
            self.last = getattr(self.last, attr)
        # Table size has increased.
        if attr in ["above", "below"]:
            self._row_count += 1
            return
        self._col_count += 1

    def insert_row(self, attr: str, field: F, row: list[F] = None) -> None:
        """ Insert row above/below of field, based on attr. """
        if row is None:
            row = self.create_empty_row()
        self._insert(attr, self.get_fields_in("h", field), row)

    def insert_col(self, attr: str, field: F, col: list[F] = None) -> None:
        """ Insert col next/right of field, based on attr. """
        if col is None:
            col = self.create_empty_col()
        self._insert(attr, self.get_fields_in("v", field), col)

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
    def from_factory_fields(cls, fields: list[TableField], **kwargs) -> B:
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
