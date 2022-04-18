from dataclasses import dataclass
from operator import attrgetter

import pandas as pd


# TODO: Move to config + make extendable
HEADER_IDENTIFIER = ["Montag - Freitag",
                     "Samstag",
                     "Sonntag",
                     "Sonn- und Feiertag"]


@dataclass
class Field:
    x0: int
    x1: int
    y0: int
    y1: int
    text: str

    def add_char(self, char: pd.Series):
        self.x1 = max(self.x1, char.x1)
        self.y0 = min(self.y0, char.y0)
        self.y1 = max(self.y1, char.y1)
        self.text += char.text

    def contains(self, other) -> bool:
        return (self.x0 <= other.x0 <= self.x1 and
                self.x0 <= other.x1 <= self.x1 and
                self.y0 <= other.y0 <= self.y1 and
                self.y0 <= other.y1 <= self.y1)


def field_from_char(char: pd.Series) -> Field:
    return Field(char.x0, char.x1, char.y0, char.y1, char.text)


class Row:
    fields: list[Field]

    def __init__(self):
        self.fields = []

    @property
    def x0(self):
        return self.fields[0].x0

    @property
    def x1(self):
        return self.fields[-1].x1

    @property
    def y0(self):
        return min([field.y0 for field in self.fields])

    @property
    def y1(self):
        return max([field.y1 for field in self.fields])

    @property
    def text(self):
        return " ".join([field.text for field in self.fields])

    @property
    def values(self):
        return self.x0, self.x1, self.y0, self.y1, self.fields

    def add(self, new_field: Field):
        i = 0
        for field in self.fields:
            if new_field.x0 < field.x0:
                break
            i += 1
        self.fields.insert(i, new_field)

    def from_list(self, fields: list[Field]):
        for field in fields:
            self.add(field)
        return self

    def get_columns(self):
        return [(field.x0, field.x1) for field in self.fields]

    def __repr__(self):
        return (f"Row(x0={self.x0}, x1={self.x1}, "
                f"y0={self.y0}, y1={self.y1}, "
                f"count={len(self.fields)}, text='{self.text}')")


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
            return ""
        format_str = "\t".join(["{:30}"] + (len(self.rows[0]) - 1) * ["{:>5}"])
        return "\n".join([format_str.format(*row) for row in self.rows])


def table_from_rows(raw_rows) -> Table:
    # Turns the list of rows of varying column count into a
    # proper table, where each row has the same number of columns.
    idx, header = _get_header(raw_rows)
    rows = _get_rows(raw_rows[idx:])
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


def _get_columns_from_row(row) -> list[Field]:
    columns = []
    for field in row.fields:
        column_field = field_from_char(field)
        column_field.text = "-"
        columns.append(column_field)
    return columns


def _get_columns_from_rows(rows):
    # Get all columns from each row
    raw_columns: list[Field] = []
    for row in rows:
        raw_columns += _get_columns_from_row(row)
    # Merge overlapping columns
    columns = []
    for current in sorted(raw_columns, key=attrgetter("x0")):
        if not columns:
            columns.append(current)
            continue
        last = columns[-1]
        if last.x0 <= current.x0 <= last.x1:
            columns[-1].x1 = max(last.x1, current.x1)
            columns[-1].y0 = min(last.y0, current.y0)
            columns[-1].y1 = max(last.y1, current.y1)
            continue
        if current.x0 >= last.x1:
            columns.append(current)
            continue
    return columns


def _get_rows(raw_rows) -> list:
    if len(raw_rows) == 0:
        return []
    # Get column fields
    """
    column_dict = {}
    for row in raw_rows:
        fields = row.fields
        for field in fields:
            column_field = field_from_char(field)
            column_field.text = ""
            column_dict[field.x0] = max(field.x1, column_dict.get(field.x0, 0))
    # Merge overlapping columns
    sorted_column_dict = sorted(column_dict.items())
    columns = [sorted_column_dict[0]]
    for start, end in sorted_column_dict[1:]:
        prev_start, prev_end = columns[-1]
        if start == prev_start and end == prev_end:
            continue
        columns.append((start, end))
    """
    columns = _get_columns_from_rows(raw_rows)
    # Get fixed size rows
    rows = []
    for raw_row in raw_rows:
        row = []
        for field_text in field_text_generator(raw_row.fields, columns):
            row.append(field_text)
        rows.append(row)

    return rows
