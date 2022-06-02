from dataclasses import dataclass
from datetime import datetime as dt

from datastructures.gtfs_output.base import BaseContainer, BaseDataClass


@dataclass
class CalendarDateEntry(BaseDataClass):
    service_id: int
    date: str
    exception_type: int

    def __init__(self, service_id: int, date: str, exception_type: int):
        super().__init__()
        self.service_id = service_id
        self.date = date
        self.exception_type = exception_type


class CalendarDates(BaseContainer):
    entries: dict[str, CalendarDateEntry]

    def __init__(self):
        super().__init__("calendar_dates.txt", CalendarDateEntry)

    def add(self, service_id: int, date: dt.date, add_service: bool
            ) -> CalendarDateEntry:
        exception_type = 1 if add_service else 2
        date_str = date.strftime("%Y%m%d")
        entry = CalendarDateEntry(service_id, date_str, exception_type)
        self._add(entry)
        return entry
