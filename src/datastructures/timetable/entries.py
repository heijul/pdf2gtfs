from config import Config
from datastructures.timetable.stops import Stop


class Weekdays:
    days: list[str]

    def __init__(self, raw_header_text: str):
        self.days = Config.header_values.get(
            raw_header_text.lower().strip(), [])

    def __repr__(self):
        return str(self.days)


class TimeTableEntry:
    def __init__(self, raw_header_text: str = "",
                 annotations_: set[str] = None) -> None:
        self._values: dict[Stop, str] = {}
        self._annotations: set[str] = annotations_ if annotations_ else set()
        self.days: Weekdays = Weekdays(raw_header_text)

    @property
    def annotations(self) -> set[str]:
        return self._annotations

    @annotations.setter
    def annotations(self, value: set[str]) -> None:
        self._annotations = value

    @property
    def values(self) -> dict[Stop, str]:
        return self._values

    def set_value(self, stop: Stop, value: str) -> None:
        self._values[stop] = value

    def get_value(self, stop: Stop) -> str | None:
        return self._values.get(stop)


class TimeTableRepeatEntry(TimeTableEntry):
    def __init__(self, raw_header_text: str = "",
                 annotations_: set[str] = None) -> None:
        super().__init__(raw_header_text, annotations_)

    @property
    def deltas(self):
        def to_int_list(_value_str):
            try:
                _values = list(map(int, _value_str.split("-")))
            except ValueError:
                return None
            if len(_values) == 2:
                return range(_values[0], _values[1] + 1)

            return [_values[0]] if len(_values) else None

        start = False
        for value_str in self.values.values():
            if value_str.lower() in Config.repeat_identifier:
                start = True
                continue
            value_str = value_str.replace(" ", "")
            if not start or not value_str:
                continue

            value = to_int_list(value_str)
            if not value:
                continue
            return value
        return []


def get_entry(raw_table, raw_column):
    import datastructures.rawtable as raw

    def get_annotations(column: raw.Column):
        _annots = set()
        for field in column.fields:
            if not isinstance(field.row, raw.AnnotationRow):
                continue
            # Splitting in case field has multiple annotations
            _annots |= set(field.text.strip().split(" "))
        return _annots

    raw_header_text = raw_table.get_header_from_column(raw_column)
    annotations = get_annotations(raw_column)
    if isinstance(raw_column, raw.RepeatColumn):
        return TimeTableRepeatEntry(raw_header_text, annotations)
    else:
        return TimeTableEntry(raw_header_text, annotations)
