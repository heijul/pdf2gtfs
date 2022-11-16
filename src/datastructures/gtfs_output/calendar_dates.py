""" Used by the handler to create the file 'calendar_dates.txt'. """

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime as dt
from pathlib import Path

import pandas as pd

from datastructures.gtfs_output import BaseContainer, BaseDataClass


@dataclass
class GTFSCalendarDateEntry(BaseDataClass):
    """ A single entry in the calendar_dates file. """
    service_id: str
    date: str
    exception_type: int

    def __init__(self, service_id: str, date: str, exception_type: int):
        super().__init__()
        self.service_id = service_id
        self.date = date
        self.exception_type = exception_type

    @staticmethod
    def from_series(s: pd.Series) -> GTFSCalendarDateEntry:
        """ Creates a new GTFSTrip from the given series. """
        return GTFSCalendarDateEntry(
            s["service_id"], s["date"], int(s["exception_type"]))


class GTFSCalendarDates(BaseContainer):
    """ Used to create the 'calendar_dates.txt'. """
    entries: list[GTFSCalendarDateEntry]

    def __init__(self, path: Path) -> None:
        super().__init__("calendar_dates.txt", GTFSCalendarDateEntry, path)

    def add(self, service_id: str, date: dt.date, add_service: bool
            ) -> GTFSCalendarDateEntry:
        """ Adds a new entry, which overrides the service with service_id
        on the given date with the given add_service value. """
        exception_type = 1 if add_service else 2
        date_str = date.strftime("%Y%m%d")
        entry = GTFSCalendarDateEntry(service_id, date_str, exception_type)
        return self._add(entry)

    def add_multiple(
            self, service_id: str, dates: list[dt.date], add_service: bool):
        """ Adds a new entry for each given date of dates. """
        for date in dates:
            self.add(service_id, date, add_service)
