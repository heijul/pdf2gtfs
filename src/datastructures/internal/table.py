from __future__ import annotations

from operator import attrgetter

from config import Config
from datastructures.internal.enums import RowType
from datastructures.internal.container import Row, Column
from datastructures.internal.lists import RowList, ColumnList
from datastructures.timetable.table import TimeTable


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

    @property
    def header_rows(self):
        return self.rows.of_type(RowType.HEADER)

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

        # Expand columns so their x-bounds are in the center between columns.
        last = columns[0] if len(columns) else None
        dist = 0
        for column in columns[1:]:
            dist = column.bbox.x0 - last.bbox.x1
            new_bound = round(last.bbox.x1 + dist / 2, 2)

            last.bbox.set("x1", new_bound)
            column.bbox.set("x0", new_bound)
            last = column
        last.bbox.set("x1", round(last.bbox.x1 + dist / 2, 2))

        self.columns = columns

        # Try to fit the 'RowTypes.OTHER'-rows into the established data rows
        #  and update their type accordingly.
        # TODO: Maybe use Config.annotation_identifier instead of this!?
        for row in self.rows:
            if row.type != RowType.OTHER:
                continue
            if row.fits_column_scheme(columns):
                row.type = RowType.ANNOTATION

    @staticmethod
    def split_rows_into_tables(rows: list[Row]) -> list[Table]:
        tables = []
        current_rows = [rows[0]]
        min_row_count = 3
        for row in rows[1:]:
            if not row.fields:
                continue
            y_distance = abs(row.distance(current_rows[-1], "y"))
            x_distance = abs(row.distance(current_rows[-1], "x"))
            if x_distance != 0 and y_distance > Config.max_row_distance:
                # TODO: Add to config
                if len(current_rows) < min_row_count:
                    # TODO: Should not drop the table,
                    #  but use it to enhance the others
                    print("Dropped rows with too much distance:\n\t"
                          "Distance (x, y):", x_distance, y_distance,
                          "Rows:", [str(r) for r in current_rows])
                    current_rows = [row]
                    continue
                print(f"Distance between rows: {y_distance}")
                tables.append(Table(current_rows))
                current_rows = []
            current_rows.append(row)
        else:
            if current_rows:
                tables.append(Table(current_rows))
        return tables

    def to_timetable(self) -> TimeTable:
        return TimeTable.from_raw_table(self)

    def get_header_from_column(self, column: Column) -> str:
        # TODO: There should be only a single header row.
        for row in self.rows.of_type(RowType.HEADER):
            for i, field in enumerate(row, 1):
                next_field = row.fields[i] if i < len(row.fields) else None
                if not next_field or next_field.bbox.x0 >= column.bbox.x1:
                    return field.text

        return ""
