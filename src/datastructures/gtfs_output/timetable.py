import pandas as pd


class TimeTable:
    value_start_idx: int = 0
    values: list
    value_end_idx: int = 0

    def __init__(self, raw_table: pd.DataFrame):
        self._set_value_indices(raw_table)
        self._get_footer_from_raw_table(raw_table)
        self.values = self.get_values(raw_table)

    def _set_value_indices(self, raw_table):
        # Start index is the first index, at which to expect a value.
        # End index is the last index + 1 at which to expect a value. (maybe oob)
        self.value_start_idx = 0
        self.value_end_idx = 0
        seen_value = False
        for row in raw_table.isna().values:
            if row[0] and not seen_value:
                self.value_start_idx += 1
            else:
                seen_value = True
            if row[0] and seen_value:
                break
            self.value_end_idx += 1

    def _get_footer_from_raw_table(self, raw_table):
        self.value_end_idx = 0
        for row in raw_table.isna().values()[self.value_start_idx:]:
            if not row[0]:
                continue
            # TODO: What if no footer?!
            self.value_end_idx += 1

    def get_values(self, raw_table):
        return raw_table[self.value_start_idx: self.value_end_idx]
