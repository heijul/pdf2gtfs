""" Provides an intermediate datastructure close to the PDF, which is used
to transform the lines in the pdf into TimeTable objects. """

from __future__ import annotations

import logging
from operator import attrgetter
from typing import Callable, TypeAlias

from config import Config
from datastructures.pdftable.container import Column, FieldContainer, Row
from datastructures.pdftable.enums import ColumnType, RowType
from datastructures.pdftable.lists import ColumnList, RowList
from datastructures.timetable.table import TimeTable


logger = logging.getLogger(__name__)
Tables: TypeAlias = list["PDFTable"]
Rows: TypeAlias = list[Row]
Cols: TypeAlias = list[Column]
Splitter: TypeAlias = Callable[[Tables, list[FieldContainer]], None]


class PDFTable:
    """ Describes a table, using coordinates, rows and columns. """
    def __init__(self, rows: Rows = None, columns: Cols = None):
        self.rows = rows or []
        self.columns = columns or []

    @property
    def rows(self) -> RowList:
        """ The rows of the table. """
        return self._rows

    @rows.setter
    def rows(self, rows: Rows | RowList) -> None:
        if isinstance(rows, RowList):
            self._rows = rows
        else:
            self._rows = RowList.from_list(self, rows)

    @property
    def columns(self) -> ColumnList:
        """ The columns of the table. """
        return self._columns

    @columns.setter
    def columns(self, columns: Cols | ColumnList):
        if isinstance(columns, ColumnList):
            self._columns = columns
        else:
            self._columns = ColumnList.from_list(self, columns)

    @property
    def empty(self) -> bool:
        """ Whether either columns or rows are empty. """
        return self.columns.empty or self.rows.empty

    def generate_columns_from_rows(self) -> None:
        """ Create columns from the given rows. """
        def _generate_single_field_columns() -> Cols:
            # Generate single-field columns from the rows.
            field_columns = [Column.from_field(self, field)
                             for row in rows for field in row]
            return sorted(field_columns, key=attrgetter("bbox.x0"))

        def _merge_overlapping_columns(field_columns: Cols) -> Cols:
            """ Merges overlapping field_columns. """
            first_field = field_columns.pop(0).fields[0]
            cols: Cols = [Column.from_field(self, first_field)]

            for column in field_columns:
                previous_column = cols[-1]
                # Begin new column, if the current column is not overlapping.
                if previous_column.bbox.x1 <= column.bbox.x0:
                    cols.append(Column.from_field(self, column.fields[0]))
                    continue

                previous_column.add_field(column.fields[0])
            return cols

        rows = self.rows.of_types(
            [RowType.DATA, RowType.ANNOTATION, RowType.ROUTE_INFO])
        if not rows:
            return

        columns = _merge_overlapping_columns(_generate_single_field_columns())
        self.columns = columns

    def fix_split_stopnames(self) -> None:
        """ Fix stop names (indented or starting with a delimiter),
        indicating they use the same city/POI as the previous stop. """
        stop_column = self.columns.of_type(ColumnType.STOP)[0]
        fields = stop_column.fields
        reference_field = fields[0]
        for field in fields[1:]:
            # Don't update the reference_field, in case field is indented.
            if not field.fix_name_if_split(reference_field):
                reference_field = field

    def to_timetable(self) -> TimeTable:
        """ Creates a TimeTable containing the values of this table. """
        return TimeTable.from_pdf_table(self)

    def get_header_from_column(self, column: Column) -> str:
        """ Returns the header text of the given column. """
        for row in self.rows.of_type(RowType.HEADER):
            for i, field in enumerate(row, 1):
                next_field = row.fields[i] if i < len(row.fields) else None
                if not next_field or next_field.bbox.x0 >= column.bbox.x1:
                    return field.text

        return ""

    def add_row_or_column(self, obj: Row | Column) -> None:
        """ Add the object to either rows or columns, based on its type. """
        if isinstance(obj, Row):
            self.rows.add(obj)
            return
        self.columns.add(obj)

    @staticmethod
    def _split_at(splitter: list, splitter_func: Splitter) -> Tables:
        tables: Tables = [PDFTable() for _ in splitter]

        splitter_func(tables, splitter)

        for table in tables:
            for row in table.rows:
                row.update_type()
            table.generate_columns_from_rows()

        return tables

    def split_at_stop_columns(self) -> Tables:
        """ Return a list of tables with each having a single stop column. """
        def splitter(tables: Tables, splitter_columns: list) -> None:
            """ Split the given tables at the given splitter_columns. """
            for row in self.rows:
                splits = row.split_at(splitter_columns)
                for table, split in zip(tables, splits):
                    if not split.fields:
                        continue
                    table.add_row_or_column(split)

        return self._split_at(self.columns.of_type(ColumnType.STOP), splitter)

    def split_at_header_rows(self) -> Tables:
        """ Return a list of tables with each having a single header row. """
        def splitter(tables: Tables, splitter_rows: list) -> None:
            """ Splits the current tables' rows such that each split starts
            with a splitter_row and assigns each split to a table. """
            rows_list = [[] for _ in splitter_rows]
            first_is_splitter = self.rows[0] in splitter_rows
            idx = -1 if first_is_splitter else 0

            for row in self.rows:
                if row in splitter_rows:
                    idx += 1
                rows_list[idx].append(row)

            for table, rows in zip(tables, rows_list, strict=True):
                table.rows = rows

        return self._split_at(self.rows.of_type(RowType.HEADER), splitter)


def split_rows_into_tables(rows: Rows) -> Tables:
    """ Split raw rows into (multiple) PDFTable. A new table is created,
    whenever the distance to the previous line is higher than the defined
    max_row_distance. Tables with too few rows are dropped with an info. """
    def log_skipped_rows() -> None:
        """ Log the rows that are dropped. """
        # FEATURE: Should not drop the table,
        #  but use it to enhance the others
        row_str = ",\n\t\t  ".join([str(r) for r in current_rows])
        logger.debug(f"Dropped rows:\n\tDistance: {y_distance:.2f}"
                     f"\n\tRows: {row_str}")

    tables = []
    current_rows = [rows[0]]
    for row in rows[1:]:
        if not row.fields:
            continue
        y_distance = row.y_distance(current_rows[-1])
        if y_distance > Config.max_row_distance:
            if len(current_rows) < Config.min_row_count:
                log_skipped_rows()
                current_rows = [row]
                continue
            logger.info(f"Distance between rows: {y_distance}")
            tables.append(PDFTable(current_rows))
            current_rows = []
        current_rows.append(row)
    else:
        if len(current_rows) < Config.min_row_count:
            log_skipped_rows()
            return tables
        tables.append(PDFTable(current_rows))
    return tables


def cleanup_tables(tables: Tables) -> Tables:
    """ Fix some errors in the tables. """
    for table in tables:
        for row in table.rows:
            row.update_type()

    tables = split_tables_with_multiple_header_rows(tables)
    for table in tables:
        table.generate_columns_from_rows()
    # TODO NOW: Handle tables which have no header row; Ask user?
    return split_tables_with_multiple_stop_columns(tables)


def split_tables_with_multiple_header_rows(tables: Tables) -> Tables:
    """ Merge table with the previous one, if it has no header row. """
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
