from __future__ import annotations

import logging
from operator import attrgetter

from config import Config
from datastructures.rawtable.enums import RowType
from datastructures.rawtable.container import Row, Column
from datastructures.rawtable.lists import RowList, ColumnList
from datastructures.timetable.table import TimeTable


logger = logging.getLogger(__name__)


class Table:
    def __init__(self, rows: list[Row] = None, columns: list[Column] = None):
        self.rows = rows or []
        self.columns = columns or []

    @property
    def rows(self) -> RowList:
        return self._rows

    @rows.setter
    def rows(self, rows: list[Row] | RowList) -> None:
        if isinstance(rows, RowList):
            self._rows = rows
        else:
            self._rows = RowList.from_list(self, rows)

    @property
    def columns(self) -> ColumnList:
        return self._columns

    @columns.setter
    def columns(self, columns: list[Column] | ColumnList):
        if isinstance(columns, ColumnList):
            self._columns = columns
        else:
            self._columns = ColumnList.from_list(self, columns)

    def generate_data_columns_from_rows(self):
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
        columns: list[Column] = []
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

        # Add the annotation fields to the columns.
        for row in self.rows.of_type(RowType.ANNOTATION):
            row.apply_column_scheme(columns)

        self.columns = columns

    def to_timetable(self) -> TimeTable:
        return TimeTable.from_raw_table(self)

    def get_header_from_column(self, column: Column) -> str:
        # TODO: What if there is more than one header row?
        for row in self.rows.of_type(RowType.HEADER):
            for i, field in enumerate(row, 1):
                next_field = row.fields[i] if i < len(row.fields) else None
                if not next_field or next_field.bbox.x0 >= column.bbox.x1:
                    return field.text

        return ""


def split_rows_into_tables(rows: list[Row]) -> list[Table]:
    tables = []
    current_rows = [rows[0]]
    for row in rows[1:]:
        if not row.fields:
            continue
        y_distance = row.distance(current_rows[-1], "y")
        if y_distance > Config.max_row_distance:
            if len(current_rows) < Config.min_row_count:
                # TODO: Should not drop the table,
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
    # TODO: Fix properly
    for table in tables:
        for row in table.rows.get_objects():
            row.detect_type()

    return remerge_tables(tables)


def remerge_tables(tables: list[Table]) -> list[Table]:
    merged_tables = []
    for table in tables:
        if table.rows.of_type(RowType.HEADER) or not merged_tables:
            merged_tables.append(table)
            continue
        merged_tables[-1].rows.merge(table.rows)

    return merged_tables
