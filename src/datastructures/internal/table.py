from itertools import cycle

import pandas as pd

from datastructures.internal.column import get_columns_from_rows
from datastructures.internal.field import field_text_generator
from datastructures.internal import Row


# TODO: Move to config + make extendable
HEADER_IDENTIFIER = ["montag - freitag",
                     "samstag",
                     "sonntag",
                     "sonn- und feiertag",
                     ]

REPEAT_IDENTIFIER = {"start": ["alle"],
                     "interval": ["num"],
                     "end": ["min", "min."],
                     }


class Table:
    def __init__(self, rows, auto_expand=True):
        self.rows = rows
        self.df = self._dataframe_from_rows()
        auto_expand = len(self.rows) if auto_expand else False
        if auto_expand:
            self._expand()

    def _dataframe_from_rows(self) -> pd.DataFrame:
        return pd.DataFrame(self.rows)

    def _expand(self):
        def __get_repeat_identifier_start_idx() -> int:
            """ Return first index where the value equals any
            repeat identifier or -1 if there is none.
            """
            cond = False
            for identifier in REPEAT_IDENTIFIER["start"]:
                cond |= column == identifier
            index = column.where(cond).dropna().index
            return index[0] if index.size else -1

        def __get_repeat_interval() -> list[int]:
            repeat_intervals = []
            current = ""
            for char in column[row_idx + 1]:
                if char.isnumeric():
                    current += char
                elif char == " ":
                    continue
                else:
                    repeat_intervals.append(int(current))
                    current = ""
            if current:
                repeat_intervals.append(int(current))
            return repeat_intervals

        # Turn "Alle x min" into proper columns.
        repeats = []
        for column_idx in self.df:
            column = self.df[column_idx]
            row_idx = __get_repeat_identifier_start_idx()

            if row_idx == -1 or row_idx + 1 > column.size:
                continue
            repeats.append((column_idx, __get_repeat_interval()))

        columns = []
        for (column_idx, intervals) in repeats:
            prev_column = pd.to_datetime(self.df[column_idx - 1], format="%H.%M")
            next_column = pd.to_datetime(self.df[column_idx + 1], format="%H.%M")
            interval_cycle = cycle([pd.Timedelta(minutes=interval)
                                    for interval in intervals])
            while True:
                column = prev_column + next(interval_cycle)
                if column[0] >= next_column[0]:
                    break
                columns.append((column_idx, column))
                prev_column = column
        for i, (column_idx, column) in enumerate(columns):
            self.df.insert(column_idx + i, f".{i}", column)
        print(self.df)
        for (column_idx, _) in repeats:
            self.df.drop(column_idx, axis=1, inplace=True)

        # Fix column names and transform columns to datetime.
        self.df.columns = range(len(self.df.columns))
        for i in self.df.columns:
            if i < 2:
                continue
            self.df[i] = pd.to_datetime(
                self.df[i], format="%H.%M", errors="coerce")

    def to_tsv(self):
        if not self.rows:
            return f"{self}; Missing rows!"
        format_str = "\t".join(["{:30}"] + (len(self.rows[0]) - 1) * ["{:>5}"])
        return "\n".join([format_str.format(*row) for row in self.rows])


def table_from_rows(raw_rows) -> Table | None:
    # Turns the list of rows of varying column count into a
    # proper table, where each row has the same number of columns.

    # TODO: Do this properly.
    # Ignore tables with too few rows.
    if len(raw_rows) < 10:
        return None

    idx, header = __get_header(raw_rows)
    row_texts = __get_row_texts(raw_rows[idx:])
    table = Table(row_texts)
    print(table.df_to_tsv())
    return table


def __get_header(raw_rows: list[Row]) -> (int, list[Row]):
    """ Returns the index of the first datarow and a list of headers. """
    header = []
    i = 0
    for row in raw_rows:
        row_text = row.text.strip().lower()
        if any([row_text.startswith(head) for head in HEADER_IDENTIFIER]):
            i += 1
            header.append(row)
            continue
        # No need to check for header if we are already at the body.
        break

    return i, header


def __get_row_texts(raw_rows: list[Row]) -> list[list[str]]:
    if len(raw_rows) == 0:
        return []

    row_texts = []
    columns = get_columns_from_rows(raw_rows)

    for raw_row in raw_rows:
        if raw_row.dropped:
            continue

        row_text = []

        for field_text in field_text_generator(raw_row.fields, columns):
            row_text.append(field_text)
        row_texts.append(row_text)

    return row_texts
