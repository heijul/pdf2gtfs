from dataclasses import dataclass
from datetime import datetime as dt

from datastructures.gtfs_output.__init__ import BaseContainer, BaseDataClass


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
    entries: list[CalendarDateEntry]

    def __init__(self):
        super().__init__("calendar_dates.txt", CalendarDateEntry)

    def add(self, service_id: int, date: dt.date, add_service: bool
            ) -> CalendarDateEntry:
        exception_type = 1 if add_service else 2
        date_str = date.strftime("%Y%m%d")
        entry = CalendarDateEntry(service_id, date_str, exception_type)
        return self._add(entry)

    def add_multiple(
            self, service_id: int, dates: list[dt.date], add_service: bool):
        for date in dates:
            self.add(service_id, date, add_service)
