from __future__ import annotations

from operator import attrgetter
from typing import Callable, Type

from more_itertools import windowed

from pdf2gtfs.datastructures.table.bounds import (
    B, EBounds, NBounds, SBounds,
    WBounds)
from pdf2gtfs.datastructures.table.fields import (
    DataField, EmptyDataField, EmptyTableField, F,
    RepeatTextField, RepeatValueField, TableField)


# TODO NOW: EXPLAAIN THESE


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

    def set_counts_from_fields(self) -> None:
        self._col_count = len(self.get_fields_in("h", self.first))
        self._row_count = len(self.get_fields_in("v", self.first))

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

    def get_nonempty_fields(self, existing_field: F, orientation: str
                            ) -> list[F]:
        """ Return the a nonempty fields in the row/col of field,
        in the given orientation. """
        # We need to have a column to search horizontally and a row
        # to search vertically or non-empty fields.
        fields = self.get_fields_in(
            "v" if orientation != "v" else "h", self.first)
        search_dir = "next" if orientation == "h" else "below"
        non_empty_fields = []
        for field in fields:
            while field and isinstance(field, EmptyTableField):
                field = getattr(field, search_dir)
            assert field and not isinstance(field, EmptyTableField)
            non_empty_fields.append(field)
        return non_empty_fields

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

    def add_new_fields_col(self, start: F, fields: list[F],
                           args: tuple[str, str] = None) -> None:
        """ Adds a new column, based on start and adds the fields.

        For this, we add an empty column, which is updated using the fields.
        """
        def check_overlap(i: int, field: F) -> bool:
            """ Check if the field overlaps vertically, with the first non-
            empty field at i and replace the corresponding border field. """
            if field and border_fields[i].bbox.is_v_overlap(field.bbox):
                self.replace(border_fields[i], field)
                return True
            return False

        def insert_between_existing(i: int, field: F) -> bool:
            """ Inserts a new, empty row for the field, if necessary. """
            if not field or border_fields[i].bbox.y0 + offset < field.bbox.y0:
                return False
            self.insert_row("above", border_fields[i])
            self.replace(border_fields[i].above, field)
            return True

        offset = 0.5
        if not args:
            assert start in (self.first, self.last)
            if start == self.first:
                args = ("next", "prev")
            else:
                args = ("prev", "next")

        self.insert_col(args[1], start)
        start = getattr(start, args[1]) if getattr(start, args[1]) else start
        border_fields = self.get_fields_in("v", start)
        fields.sort(key=attrgetter("bbox.y0"), reverse=True)

        assert all((isinstance(f, EmptyTableField) for f in border_fields))
        self.add_new_fields(
            fields, self.row_count, check_overlap, insert_between_existing)

    def add_new_fields_row(
            self, start: F, fields: list[F], args: tuple[str, str] = None
            ) -> None:
        def check_overlap(i: int, field: F) -> bool:
            """ Check if the field overlaps horizontally, with the first non-
            empty field at i and replace the corresponding border field. """
            if field and border_fields[i].bbox.is_h_overlap(field.bbox):
                self.replace(border_fields[i], field)
                return True
            return False

        def insert_between_existing(i: int, field: F) -> bool:
            """ Inserts a new, empty column for the field, if necessary. """
            if not field or border_fields[i].bbox.x0 + offset < field.bbox.x0:
                return False
            self.insert_col("prev", border_fields[i])
            self.replace(border_fields[i].prev, field)
            return True

        offset = 0.5
        if not args:
            assert start in (self.first, self.last)
            if start == self.first:
                args = ("below", "above")
            else:
                args = ("above", "below")

        self.insert_row(args[1], start)
        start = getattr(start, args[1]) if getattr(start, args[1]) else start
        border_fields = self.get_fields_in("h", start)
        fields.sort(key=attrgetter("bbox.x0"), reverse=True)

        assert all((isinstance(f, EmptyTableField) for f in border_fields))
        self.add_new_fields(
            fields, self.col_count, check_overlap, insert_between_existing)

    def try_add_fields(self, bounds_cls: Type[B], start: F, fields: list[F],
                       search_dir: str, add_func: Callable[[F, list[F]], None]
                       ) -> bool:
        data_fields = self.get_fields_in(search_dir, start)
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
        return self.try_add_fields(WBounds, self.first, fields, "v",
                                   self.add_new_fields_col)

    def grow_east(self, fields: list[TableField]) -> bool:
        """ Tries to insert the fields, if they are right of the table. """
        return self.try_add_fields(EBounds, self.last, fields, "v",
                                   self.add_new_fields_col)

    def grow_north(self, fields: list[TableField]) -> bool:
        """ Tries to insert the fields, if they are above the table. """
        return self.try_add_fields(NBounds, self.first, fields, "h",
                                   self.add_new_fields_row)

    def grow_south(self, fields: list[TableField]) -> bool:
        """ Tries to insert the fields, if they are below the table. """
        return self.try_add_fields(SBounds, self.last, fields, "h",
                                   self.add_new_fields_row)

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

    @staticmethod
    def _split(field_lists: list[list[F]], counts: slice,
               create_func: Callable[[list[list[F]]], TableFactory]
               ) -> list[TableFactory]:
        """ Split the given field_lists into multiple lists, such that each
        of them has a length of counts[1]. Afterwards creates a list of
        TableFactory, using the fields and the create_func.
        """
        splits = []
        for i in range(counts.start, counts.stop, counts.step):
            splits.append(field_lists[i:i + counts.step])

        factories = [create_func(split) for split in splits]
        return factories

    def split_horizontal(self, row_count: int) -> list[TableFactory]:
        """ Split the table into multiple, such that each (except possibly
        the last) have exactly row_count rows. """
        first_col = self.get_fields_in("v", self.first)
        rows = [self.get_fields_in("h", field) for field in first_col]
        return self._split(
            rows, slice(0, self.row_count, row_count), self.from_rows)

    def split_vertical(self, col_count: int) -> list[TableFactory]:
        """ Split the table into multiple, such that each (except possibly
        the last) have exactly col_count columns. """
        first_row = self.get_fields_in("h", self.first)
        cols = [self.get_fields_in("v", field) for field in first_row]
        return self._split(
            cols, slice(0, self.col_count, col_count), self.from_cols)

    @staticmethod
    def _from_fields(field_lists: list[list[F]],
                     clear_vals: list[tuple[int, str]]) -> TableFactory:
        """ Creates a new valid factory, using the given field_lists,
        which are either lists of cols or lists of rows. """
        factory = TableFactory()
        # Remove references to other fields.
        for clear_id, clear_attr in clear_vals:
            for field in field_lists[clear_id]:
                setattr(field, clear_attr, None)
        # Set owner to new factory.
        for field_list in field_lists:
            for field in field_list:
                field.owner = factory
        factory.first = field_lists[0][0]
        factory.last = field_lists[-1][-1]
        factory.set_counts_from_fields()
        return factory

    @staticmethod
    def from_rows(rows: list[list[F]]) -> TableFactory:
        """ Construct a new table, given the valid rows. """
        return TableFactory._from_fields(rows, [(0, "above"), (-1, "below")])

    @staticmethod
    def from_cols(cols: list[list[F]]) -> TableFactory:
        """ Construct a new table, given the valid cols. """
        return TableFactory._from_fields(cols, [(0, "prev"), (-1, "next")])

    def get_contained_fields(self, fields: list[F]) -> list[F]:
        non_empty_col = self.get_fields_in("v", self.first)
        bounds = WBounds.from_factory_fields(non_empty_col)
        bounds.expand(EBounds.from_factory_fields(non_empty_col))
        non_empty_row = self.get_fields_in("h", self.first)
        bounds.expand(NBounds.from_factory_fields(non_empty_row))
        bounds.expand(SBounds.from_factory_fields(non_empty_row))
        print(bounds)
        fields = list(filter(bounds.within_bounds, fields))
        return fields

    @staticmethod
    def find_repeat_fields(fields: list[F]) -> list[tuple[F, F, F]]:
        """ Takes a list of fields contained within the table and adds those
        fields to the table, that conform to the repeated-fields format.  """
        # Look for repeat columns.
        fields.sort(key=attrgetter("bbox.y0", "bbox.x0"))
        # Get all fields, that are not horizontally overlapping.
        overlaps = []
        for field in fields:
            is_overlapping = False
            for overlap in overlaps:
                if overlap[0].bbox.is_h_overlap(field.bbox):
                    overlap.append(field)
                    is_overlapping = True
            if not is_overlapping:
                overlaps.append([field])

        # noinspection PyTypeChecker
        repeat_fields: list[tuple[F, F, F]] = []
        for overlap in overlaps:
            for top, mid, bot in windowed(overlap, 3):
                if (top.text.lower().strip() != "alle" or
                        bot.text.lower().strip() != "min." or
                        not mid.text.isnumeric()):
                    continue
                # Convert each field to RepeatText-/RepeatValueField.
                fields.remove(top)
                fields.remove(mid)
                fields.remove(bot)
                repeat_fields.append((top.to_subtype(RepeatTextField),
                                      mid.to_subtype(RepeatValueField),
                                      bot.to_subtype(RepeatTextField)))
                # TODO NOW: Add top/mid/bot to each other.
        return repeat_fields

    def add_repeat_fields(self, fields: list[tuple[F, F, F]]) -> None:
        for top, mid, bot in fields:
            bbox = top.bbox.copy().merge(mid.bbox).merge(bot.bbox)
            current = self.first
            while True:
                if current is None:
                    print(f"Did not add repeat fields {top}, {mid}, {bot},"
                          "because they are outside the table.")
                    break
                if current.bbox.is_h_overlap(bbox):
                    continue
                    self.add_fields_to_col(current, [top, mid, bot])
                    break
                if current.bbox.x0 > bbox.x0:
                    self.add_new_fields_col(current, [top, mid, bot],
                                            ("prev", "prev"))
                    break
                current = current.next

    def check_which_splits(self, fields: list[F]) -> list[F]:
        # Check which fields are overlapping table cols.
        overlapping_rows = []
        for col_field in self.get_fields_in("v", self.first):
            overlapping_rows += [f for f in fields
                                 if col_field.bbox.is_v_overlap(f.bbox)
                                 and f not in overlapping_rows]
        # Check which fields are overlapping table rows.
        overlapping_cols = []
        for row_field in self.get_fields_in("h", self.first):
            overlapping_cols += [f for f in fields
                                 if row_field.bbox.is_h_overlap(f.bbox)
                                 and f not in overlapping_cols]
        return [f for f in fields
                if (overlapping_rows.count(f) + overlapping_cols.count(f)) < 2]

    def split_at_field(self):
        ...

    def split_at_contained_rows(self, fields: list[F]) -> list[TableFactory]:
        # Get containned fields.
        c_fields = self.get_contained_fields(fields)
        # Remove contained fields from fields.
        for field in c_fields:
            fields.remove(field)
        print(fields)
        # Check c_fields for RepeatFields and add them to the table.
        repeat_fields = self.find_repeat_fields(c_fields)
        self.add_repeat_fields(repeat_fields)
        # Check for remaining c_fields, if they split the table.
        splitter_fields = self.check_which_splits(c_fields)
        print(splitter_fields)
        # Split the table at the splitfields.
        ...
        return self.split_horizontal(11)
