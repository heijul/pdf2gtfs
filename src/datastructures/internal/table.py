from operator import attrgetter
from statistics import mean

from datastructures.internal.column import Column, column_from_field
from datastructures.internal.row import Row


# TODO: Move to config + make extendable
HEADER_IDENTIFIER = ["Montag - Freitag",
                     "Samstag",
                     "Sonntag",
                     "Sonn- und Feiertag"]


class Table:
    def __init__(self, rows, auto_expand=True):
        self.rows = rows
        if auto_expand:
            self._expand()

    def _expand(self):
        # Turn "Alle x min" into proper columns.
        ...

    def to_tsv(self):
        if not self.rows:
            return f"{self}; Missing rows!"
        format_str = "\t".join(["{:30}"] + (len(self.rows[0]) - 1) * ["{:>5}"])
        return "\n".join([format_str.format(*row) for row in self.rows])


def table_from_rows(raw_rows) -> Table:
    # Turns the list of rows of varying column count into a
    # proper table, where each row has the same number of columns.
    idx, header = _get_header(raw_rows)
    rows, dropped_rows = _get_rows(raw_rows[idx:])
    table = Table(rows)
    print(table.to_tsv())
    return table


def _get_header(raw_rows) -> (int, list[Row]):
    header = []
    i = 0
    for row in raw_rows:
        row_text = row.text.strip()
        if any([row_text.startswith(head) for head in HEADER_IDENTIFIER]):
            i += 1
            header.append(row)
            continue
        break
    return i, header


def field_text_generator(fields, columns):
    field_index = 0
    column_index = 0
    while field_index < len(fields) or column_index < len(columns):
        column = columns[column_index]
        column_index += 1
        text = ""
        # Needed in case multiple fields are within the current column
        while (field_index < len(fields)
               and column.contains(fields[field_index])):
            text += fields[field_index].text
            field_index += 1

        yield text if text else column.text


def _get_columns_from_row(row) -> list[Column]:
    columns = []
    for field in row.fields:
        column = column_from_field(field)
        columns.append(column)
    return columns


def _get_columns_from_rows(rows):
    # Get all columns from each row
    raw_columns = [_get_columns_from_row(row) for row in rows]
    clean_columns = drop_invalid_rows(raw_columns, rows)
    return merge_columns(clean_columns)


def drop_invalid_rows(raw_columns: list[list[Column]], rows: list[Row]
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


def merge_columns(clean_columns: list[Column]):
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


def _get_rows(raw_rows) -> (list[str], list[Row]):
    if len(raw_rows) == 0:
        return []
    columns = _get_columns_from_rows(raw_rows)
    # Get fixed size rows
    rows = []
    for raw_row in raw_rows:
        if raw_row.dropped:
            continue
        row = []
        for field_text in field_text_generator(raw_row.fields, columns):
            row.append(field_text)
        rows.append(row)

    return rows, [row for row in raw_rows if row.dropped]
