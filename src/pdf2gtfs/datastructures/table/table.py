from __future__ import annotations

from operator import attrgetter, methodcaller
from typing import Callable, Type, TypeAlias

from more_itertools import pad_none, partition, peekable, spy, windowed

from pdf2gtfs.datastructures.table.bounds import (
    B, EBounds, NBounds, SBounds, WBounds)
from pdf2gtfs.datastructures.table.container import C, Col, Cols, Row, Rows
from pdf2gtfs.datastructures.table.fields import (
    DataField, EmptyDataField, EmptyTableField, F,
    RepeatTextField, RepeatValueField, TableField)


class Table:
    """ A single table, defined by its rows and columns. """
    def __init__(self, rows: Rows, cols: Cols) -> None:
        self.rows: Rows = rows
        self.cols: Cols = cols

    def expand(self, bounds_cls: Type[B], row_or_col: C, fields: list[F]
               ) -> None:
        adjacent_fields = bounds_cls.select_adjacent_fields(row_or_col, fields)

        # Remove added fields from the list of potential fields.
        for field in adjacent_fields:
            fields.remove(field)

    def expand_w(self, fields: list[F]) -> None:
        """ Add those fields to the table, that are adjacent to it.

        :param fields: Fields that are not part of the table and may
         or may not be adjacent to it.
        """
        col = self.cols.first
        adj_fields = WBounds.select_adjacent_fields(col, fields)
        if not adj_fields:
            return
        # Remove added fields from the list of potential fields.
        for field in adj_fields:
            fields.remove(field)

        func = methodcaller("bbox.is_v_overlap", relative_amount=0.66)
        in_between_fields, overlapping_fields = partition(func, adj_fields)
        new_col = col.construct_from_overlapping_fields(overlapping_fields)
        self.cols.prepend(self.cols.first, node=new_col)


class TableFactory:
    """ A factory, that uses the ability to rigidly detect datafields in a
    table, in order to create one or more tables. """
    def __init__(self) -> None:
        self.rows: Rows = Rows()
        self.cols: Cols = Cols()

    @property
    def row_count(self) -> int:
        """ Number of fields in each column. """
        return len(self.rows)

    @property
    def col_count(self) -> int:
        """ Number of fields in each row. """
        return len(self.cols)

    @staticmethod
    def set_datafield_positions(fields: list[DataField]) -> tuple[int, int]:
        """ Calculate the row- and column-ids of each datafield.

        :param fields:
        :return: The number of columns and rows.
        """
        # Get the columns, based on how much a field overlaps horizontally
        # with the first (= left-most) field of each column.
        fields = sorted(fields, key=attrgetter("bbox.x0", "bbox.y0"))
        column_starter = fields[0]
        col_id = 0
        for field in fields:
            # If a field does not overlap horizontally, start a new column.
            if not column_starter.bbox.is_h_overlap(field.bbox):
                column_starter = field
                col_id += 1
            field.col_id = col_id
        col_count = col_id + 1
        # Get the rows, based on how much a field overlaps vertically
        # with the first (= highest) field in each row.
        row_id = 0
        fields = sorted(fields, key=attrgetter("bbox.y0", "bbox.x0"))
        row_starter = fields[0]
        for field in fields:
            # If a field does not overlap vertically, start a new row.
            if not row_starter.bbox.is_v_overlap(field.bbox):
                row_starter = field
                row_id += 1
            field.row_id = row_id
        row_count = row_id + 1
        return col_count, row_count

    @staticmethod
    def fill_grid(fields: list[DataField], col_count: int) -> list[F]:
        """ Add empty fields to the list of fields, such that each column has
        col_count fields, while maintaining the structure (i.e. the relative
        position of fields to each other) of the table.

        :param fields: The fields containing the time data.
        :param col_count: The number of columns the table should have.
        :return: A list of DataField/EmptyDataField, which is roughly
         equivalent to flattening a list of columns.
        """
        (head,), fields = spy(
            sorted(fields, key=attrgetter("row_id", "col_id")))
        peeker = peekable(fields)
        # Add fields, in case the first field is not in the first column.
        grid: list[DataField] = [EmptyDataField() for _ in range(head.col_id)]
        for field in peeker:
            grid.append(field)
            next_field = peeker.peek(None)
            if next_field is None:
                # We need to add fields at the end, if the
                # last field is not in the last column.
                count = col_count - field.col_id
            elif next_field.row_id > field.row_id:
                # We need to add fields after field, if it is not in the last
                # column and before next_field, if it is not in the first.
                count = col_count + next_field.col_id - field.col_id
            else:
                # We only need to add fields in between.
                count = next_field.col_id - field.col_id
            for _ in range(count - 1):
                grid.append(EmptyDataField())
            # These are only required for the initial table creation.
            del field.row_id
            del field.col_id
        return grid

    def create_container_from_grid(self, grid: list[DataField],
                                   row_count: int, col_count: int) -> None:
        """ Create the cols/rows for this TableFactory.

        :param grid: A complete list, containing all DataFields. Its length
         should be row_count * col_count.
        :param row_count: The number of rows the table should have.
        :param col_count: The number of cols the table should have.
        """
        for i in range(col_count):
            fields = grid[i:col_count * row_count:col_count]
            self.cols.append(Col.from_objects(fields))
        for i in range(row_count):
            fields = grid[i * col_count:i * col_count + col_count]
            self.rows.append(Row.from_objects(fields))

    @staticmethod
    def from_datafields(fields: list[DataField]) -> TableFactory:
        """ Uses the provided fields to create a tablefactory.

        :param fields: All
        :return: A tablefactory, that contains only
         DataFields and EmptyDataFields.
        """
        factory = TableFactory()
        col_count, row_count = factory.set_datafield_positions(fields)
        grid = factory.fill_grid(fields, col_count)
        factory.create_container_from_grid(grid, row_count, col_count)
        # This needs to be done, even if it has been done while adding an
        # empty field, because the bboxes of the rows/cols may have changed.
        for row in factory.rows:
            row.set_empty_field_bboxes()
        return factory

    def print_fields(self, max_field_length: int = 5,
                     max_line_length: int = 180) -> None:
        """ Print the table in a human-readable way to stdout.

        :param max_field_length: The maximum length of a field,
         before it is truncated.
        :param max_line_length: The maximum length of a line,
         before it is truncated
        """
        def col_width(col: Col) -> int:
            """ Calculate the width of a column, such that it can contain all
            of its fields' texts.

            :param col: The column in question.
            :return: The number of chars the column has to contain.
            """
            return max([len(field.text[:max_field_length])
                        for field in col])

        def alignment(field: TableField) -> str:
            """ Decide how to align the fields' text, based on its type.

            :param field: The field in question.
            :return: Right-align DataFields and left-align all other fields.
            """
            if isinstance(field, DataField):
                return ">"
            return "<"

        delim = " | "
        lines = [delim.join(
            [f"{f.text[:max_field_length]: {alignment(f)}{col_width(f.col)}}"
             for f in row]) for row in self.rows]
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

    def grow_west2(self, fields: list[F]) -> bool:
        new_fields = self._grow(WBounds, list(self.cols[0]), fields)
        if not new_fields:
            return False
        self.cols.insert(0, self.cols[0].create_before_from_fields(new_fields))
        return True

    def add_fields_left(self, new_fields: list[F]) -> None:
        fields = []
        new_fields = pad_none(new_fields)
        new_field = next(new_fields)
        i = 0
        while i < len(self.rows):
            row = self.rows[i]
            if new_field and row.bbox.is_v_overlap(new_field.bbox):
                fields.append(new_field)
                # The next new_field may be in the same row.
                new_field = next(new_fields)
                continue
            if new_field and row.comes_after(new_field):
                # Using insert here, will use the current row in
                # the next iteration as well.
                row = row.create_from_field(new_field)
                self.rows.insert(i, row)
                new_field = next(new_fields)
                continue
            e_field = EmptyTableField()
            e_field.row = row
            fields.append(e_field)
            # Only increment, if we add an empty field, in case two
            # consecutive fields overlap the same row or are between two rows.
            i += 1

        self.cols[0].create_above_from_fields(fields)

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
        factory.first = field_lists[0][0]
        factory.last = field_lists[-1][-1]
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
        bounds.merge(EBounds.from_factory_fields(non_empty_col))
        non_empty_row = self.get_fields_in("h", self.first)
        bounds.merge(NBounds.from_factory_fields(non_empty_row))
        bounds.merge(SBounds.from_factory_fields(non_empty_row))
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


T: TypeAlias = TableFactory
