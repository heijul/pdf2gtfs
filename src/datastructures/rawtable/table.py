from __future__ import annotations

import logging
from operator import attrgetter
from typing import TypeAlias

from config import Config
from datastructures.rawtable.container import Column, Row
from datastructures.rawtable.enums import ColumnType, RowType
from datastructures.rawtable.lists import ColumnList, RowList
from datastructures.timetable.table import TimeTable


logger = logging.getLogger(__name__)
Tables: TypeAlias = list["Table"]
Rows: TypeAlias = list[Row]
Cols: TypeAlias = list[Column]


class Table:
    def __init__(self, rows: Rows = None, columns: Cols = None):
        self.rows = rows or []
        self.columns = columns or []

    @property
    def rows(self) -> RowList:
        return self._rows

    @rows.setter
    def rows(self, rows: Rows | RowList) -> None:
        if isinstance(rows, RowList):
            self._rows = rows
        else:
            self._rows = RowList.from_list(self, rows)

    @property
    def columns(self) -> ColumnList:
        return self._columns

    @columns.setter
    def columns(self, columns: Cols | ColumnList):
        if isinstance(columns, ColumnList):
            self._columns = columns
        else:
            self._columns = ColumnList.from_list(self, columns)

    def generate_data_columns_from_rows(self) -> None:
        def _get_bounds(_column: Column):
            return _column.bbox.x0, _column.bbox.x1

        def _column_x_is_overlapping(_c1: Column, field_column: Column):
            b1 = _get_bounds(_c1)
            b2 = _get_bounds(field_column)
            # Do not use equality here to prevent returning true
            #  for columns that are only touching.
            return b1[0] <= b2[0] <= b1[1] or b1[0] <= b2[1] <= b1[1]

        data_rows = self.rows.of_type(RowType.DATA)
        if not data_rows:
            return

        # Generate single-field columns from the rows.
        field_columns = [Column.from_field(self, field)
                         for row in data_rows for field in row]

        # Merge vertically overlapping columns.
        columns: Cols = []
        for column in sorted(field_columns, key=attrgetter("bbox.x0")):
            if not columns:
                columns.append(Column.from_field(self, column.fields[0]))
                continue
            last = columns[-1]
            # Do not try to merge columns in the same row.
            if last.bbox.x1 <= column.bbox.x0:
                columns.append(Column.from_field(self, column.fields[0]))
                continue
            if _column_x_is_overlapping(last, column):
                last.add_field(column.fields[0])

        self.columns = columns
        # Add the annotation fields to the columns.
        for row in self.rows.of_types([RowType.ANNOTATION,
                                       RowType.ROUTE_INFO]):
            row.apply_column_scheme(columns)

    def fix_split_stopnames(self) -> None:
        """ Finds and tries to repair stop names, which start with a "-",
         indicating that they use the same city/poi as the previous.

        E.g. given a row with stop A with text "Frankfurt - Hauptbahnhof",
         followed by a stop B with text "- Friedhof", then the text of B
         will be changed to "Frankfurt - Friedhof".
        """

        def get_base_name(prev_text: str, text: str) -> str:
            """ Returns the base name for the split stops.
            I.e. the 'Frankfurt' in the example above. """
            text = text.strip()
            # Current text is equal to previous stop, but the short version.
            if text in prev_text:
                return prev_text.replace(text, "")
            # Current text without delimiter is contained in previous stop.
            clean_text = text[1:].strip()
            if clean_text in prev_text:
                return prev_text.replace(clean_text, "")
            # Current stop is different from previous stop.
            return _get_base_from_last_stop_text(prev_text)

        def _get_base_from_last_stop_text(prev_text: str) -> str:
            """ Find the most likely base_text of a given text, by splitting
            the text at common delimiters. """
            split_chars = [",", "-", " "]
            for split_char in split_chars:
                split_text = prev_text.split(split_char, 1)
                if len(split_text) <= 1:
                    continue
                return split_text[0].strip()
            return prev_text.strip()

        def is_indented() -> bool:
            min_indention_in_pts = 3
            dist = abs(stop_columns[0].bbox.x0 - stop.bbox.x0)
            return dist >= min_indention_in_pts

        stop_columns = self.columns.of_type(ColumnType.STOP)
        if not stop_columns or not stop_columns[0].fields:
            return

        stops = stop_columns[0].fields
        prev_stop_text = stops[0].text
        base_text = ""
        for stop in stops[1:]:
            stop_text = stop.text.strip()
            if not stop_text or stop.row.type != RowType.DATA:
                continue
            is_normal_stop = not (stop_text.startswith("-") or is_indented())
            if is_normal_stop:
                prev_stop_text = stop_text
                base_text = ""
                continue
            # Need to save the base_stop_name,
            #  in case multiple consecutive stops are split
            if not base_text:
                base_text = get_base_name(prev_stop_text, stop_text)
            stop.text = base_text + ", " + stop_text[1:].strip()

    def to_timetable(self) -> TimeTable:
        return TimeTable.from_raw_table(self)

    def get_header_from_column(self, column: Column) -> str:
        for row in self.rows.of_type(RowType.HEADER):
            for i, field in enumerate(row, 1):
                next_field = row.fields[i] if i < len(row.fields) else None
                if not next_field or next_field.bbox.x0 >= column.bbox.x1:
                    return field.text

        return ""

    def add_row_or_column(self, obj: Row | Column) -> None:
        if isinstance(obj, Row):
            self.rows.add(obj)
            return
        self.columns.add(obj)

    def _split_at(self, splitter: Rows | Cols) -> Tables:
        """ Split the table at the given splitter. """
        tables = [Table() for _ in splitter]
        objects = self.columns if isinstance(splitter[0], Row) else self.rows

        for obj in objects:
            splits = obj.split_at(splitter)
            for table, split in zip(tables, splits):
                table.add_row_or_column(split)

        for table in tables:
            for row in table.rows:
                row.update_type()
            table.generate_data_columns_from_rows()
        return tables

    def split_at_stop_columns(self) -> Tables:
        """ Return a list of tables with each having a single stop column. """
        return self._split_at(self.columns.of_type(ColumnType.STOP))

    def split_at_header_rows(self) -> Tables:
        """ Return a list of tables with each having a single header row. """
        return self._split_at(self.rows.of_type(RowType.HEADER))


def split_rows_into_tables(rows: Rows) -> Tables:
    tables = []
    current_rows = [rows[0]]
    for row in rows[1:]:
        if not row.fields:
            continue
        y_distance = row.y_distance(current_rows[-1])
        if y_distance > Config.max_row_distance:
            if len(current_rows) < Config.min_row_count:
                # FEATURE: Should not drop the table,
                #  but use it to enhance the others
                row_str = ",\n\t\t  ".join([str(r) for r in current_rows])
                logger.debug(f"Dropped rows:\n\tDistance: {y_distance}"
                             f"\n\tRows: {row_str}")
                current_rows = [row]
                continue
            logger.info(f"Distance between rows: {y_distance}")
            tables.append(Table(current_rows))
            current_rows = []
        current_rows.append(row)
    else:
        if current_rows:
            tables.append(Table(current_rows))
    return tables


def cleanup_tables(tables: Tables) -> Tables:
    """ Fix some errors in the tables. """
    for table in tables:
        for row in table.rows.get_objects():
            row.update_type()

    tables = enforce_single_header_row(tables)
    for table in tables:
        table.generate_data_columns_from_rows()
    # TODO: Handle tables which have no header row; Ask user?
    return split_tables_with_multiple_stop_columns(tables)


def enforce_single_header_row(tables: Tables) -> Tables:
    """ Merge tables with the previous one, if it has no header row. """
    if not tables:
        return []

    merged_tables: Tables = [tables[0]]
    for table in tables[1:]:
        header_rows = table.rows.of_type(RowType.HEADER)
        if len(header_rows) > 1:
            merged_tables += table.split_at_header_rows()
            continue
        if header_rows:
            merged_tables.append(table)
            continue
        merged_tables[-1].rows.merge(table.rows)

    return merged_tables


def split_tables_with_multiple_stop_columns(tables: Tables) -> Tables:
    """ If a table has multiple stop columns, it will be split into two
    tables with each having only one stop column. """
    split_tables = []
    for table in tables:
        stop_columns = table.columns.of_type(ColumnType.STOP)
        if len(stop_columns) <= 1:
            split_tables.append(table)
            continue
        split_tables += table.split_at_stop_columns()
    return split_tables
