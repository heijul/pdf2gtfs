from operator import attrgetter
from statistics import mean

from datastructures.internal.field import Field, Column
from datastructures.internal.row import Row


def column_from_field(field: Field, text: str = "-") -> Column:
    return Column(field.x0, field.x1, field.y0, field.y1, text)


def get_columns_from_rows(rows: list[Row]):
    # Get all columns from each row
    raw_columns = [__get_columns_from_row(row) for row in rows]
    clean_columns = __drop_invalid_rows(raw_columns, rows)
    return __merge_columns(clean_columns)


def __merge_columns(clean_columns: list[Column]):
    # Merge overlapping columns
    columns = []
    for column in sorted(clean_columns, key=attrgetter("x0")):
        if not columns:
            columns.append(column)
            continue
        last = columns[-1]
        if last.x0 <= column.x0 <= last.x1:
            columns[-1].x1 = max(last.x1, column.x1)
            columns[-1].y0 = min(last.y0, column.y0)
            columns[-1].y1 = max(last.y1, column.y1)
            continue
        if column.x0 >= last.x1:
            columns.append(column)
            continue
    return columns


def __get_columns_from_row(row) -> list[Column]:
    columns = []
    for field in row.fields:
        column = column_from_field(field)
        columns.append(column)
    return columns


def __drop_invalid_rows(raw_columns: list[list[Column]], rows: list[Row]
                        ) -> (list[Column], list):
    def dissimilar() -> bool:
        # TODO: Add constant/config instead of magic number.
        return (count / count_mean) < 0.5

    # Drop rows, with columns which are too dissimilar from the others
    counts = [len(columns) for columns in raw_columns]
    count_mean = mean(counts)
    clean_columns = []

    for i, (row, count) in enumerate(zip(rows, counts)):
        if dissimilar():
            row.dropped = True
            continue
        clean_columns += raw_columns[i]

    return clean_columns
