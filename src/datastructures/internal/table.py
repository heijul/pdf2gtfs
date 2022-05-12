from itertools import cycle
from statistics import mean

import pandas as pd

from datastructures.internal.column import get_columns_from_rows
from datastructures.internal.field import field_text_generator
from datastructures.internal import Row
from config import Config


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
            for identifier in Config.repeat_identifier:
                cond |= column == identifier
            index = column.where(cond).dropna().index
            return index[0] if index.size else -1

        def __get_repeat_interval() -> list[int]:
            # TODO: Should " ".join the whole column.
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
            if Config.repeat_strategy == "mean":
                return [mean(repeat_intervals)]
            return repeat_intervals

        def df_to_csv():
            # Basically does what pd.DataFrame.to_csv does but returns it
            #  as string. Only for demonstration purposes.
            format_str = "\t".join(["{:30}"] +
                                   (self.df.columns.size - 1) * ["{:>5}"])
            times = []
            for _, series in self.df.iterrows():
                times.append([])
                for field in series:
                    text = str(field)
                    if isinstance(field, pd.Timestamp):
                        text = field.strftime("%H:%M")
                    elif field is pd.NaT:
                        text = ""
                    times[-1].append(text)
            return "\n".join([format_str.format(*row) for row in times])

        def get_timedelta(_interval):
            _minutes = int(_interval)
            _seconds = round((_interval - _minutes) * 60)
            return pd.Timedelta(minutes=_minutes, seconds=_seconds)

        # TODO: Split this into multiple functions/Create class RepeatColumn.
        #  Timedeltas probably need to use the proper year/day, so will need
        #  to do the actual expansion later...
        # Turn "Alle x min" into proper columns.
        # Get the indices of all columns, which contain a repeat identifier.
        repeats = []
        for column_idx in self.df:
            column = self.df[column_idx]
            row_idx = __get_repeat_identifier_start_idx()

            if row_idx == -1 or row_idx + 1 > column.size:
                continue
            repeats.append((column_idx, __get_repeat_interval()))

        # Repeatedly apply the interval to the previous column.
        columns = []
        for (column_idx, intervals) in repeats:
            prev_column = pd.to_datetime(self.df[column_idx - 1],
                                         format=Config.time_format)
            next_column = pd.to_datetime(self.df[column_idx + 1],
                                         format=Config.time_format)
            interval_cycle = cycle(
                [get_timedelta(interval) for interval in intervals])
            while True:
                column = prev_column + next(interval_cycle)
                if column[0] >= next_column[0]:
                    break
                columns.append((column_idx, column))
                prev_column = column

        # Insert the repeated columns into their proper position.
        for i, (column_idx, column) in enumerate(columns):
            self.df.insert(column_idx + i, f".{i}", column)

        print(self.df)
        # Remove all columns, which contain the repeat identifier.
        for (column_idx, _) in repeats:
            self.df.drop(column_idx, axis=1, inplace=True)

        # Fix column names and transform columns to datetime.
        self.df.columns = range(len(self.df.columns))
        for i in self.df.columns:
            if i < 2:
                continue
            # TODO: Errors should be handled properly
            self.df[i] = pd.to_datetime(
                self.df[i], format=Config.time_format, errors="coerce")
        print(df_to_csv())

    def to_csv(self):
        if not self.rows:
            return f"{self}; Missing rows!"
        format_str = "\t".join(["{:30}"] + (len(self.rows[0]) - 1) * ["{:>5}"])
        return "\n".join([format_str.format(*row) for row in self.rows])


def table_from_rows(raw_rows) -> Table | None:
    # Turns the list of rows of varying column count into a
    # proper table, where each row has the same number of columns.

    # TODO: Do this properly.
    # Ignore tables with too few rows.
    if len(raw_rows) < Config.min_table_rows:
        return None

    idx, header = __get_header(raw_rows)
    row_texts = __get_row_texts(raw_rows[idx:])
    table = Table(row_texts)
    print(table.to_csv())
    return table


def __get_header(raw_rows: list[Row]) -> (int, list[Row]):
    """ Returns the index of the first datarow and a list of headers. """
    header = []
    i = 0
    for row in raw_rows:
        row_text = row.text.strip().lower()
        if any([row_text.startswith(head)
                for head in Config.header_identifier]):
            i += 1
            header.append(row)
            continue
        # No need to check for a header if we are already at the body.
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
