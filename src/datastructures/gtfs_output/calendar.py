from __future__ import annotations

import datetime as dt
from dataclasses import fields, dataclass
from typing import TypeAlias, Callable

from config import Config
from datastructures.gtfs_output.__init__ import BaseContainer, BaseDataClass


@dataclass
class DayIsActive:
    active: bool = True

    def __eq__(self, other: DayIsActive) -> bool:
        return self.active == other.active

    def to_output(self) -> str:
        return str(int(self.active))

    def __repr__(self):
        return self.to_output()


class ServiceDay:
    def __init__(self, date: dt.date):
        self.date = date

    def to_output(self) -> str:
        return self.date.strftime("%Y%m%d")

    def __eq__(self, other: ServiceDay):
        return self.date == other.date

    def __repr__(self):
        return self.to_output()


class StartDate(ServiceDay):
    def __init__(self):
        super().__init__(Config.gtfs_date_bounds[0])


class EndDate(ServiceDay):
    def __init__(self):
        super().__init__(Config.gtfs_date_bounds[1])


@dataclass(init=False)
class CalendarEntry(BaseDataClass):
    service_id: int
    monday: DayIsActive = DayIsActive(False)
    tuesday: DayIsActive = DayIsActive(False)
    wednesday: DayIsActive = DayIsActive(False)
    thursday: DayIsActive = DayIsActive(False)
    friday: DayIsActive = DayIsActive(False)
    saturday: DayIsActive = DayIsActive(False)
    sunday: DayIsActive = DayIsActive(False)
    start_date: ServiceDay = StartDate()
    end_date: ServiceDay = EndDate()

    def __init__(self, annots: set[str] | None = None):
        super().__init__()
        self.service_id = self.id
        self.on_holidays = False
        self.annotations = annots or set()
        self.start_date = StartDate()
        self.end_date = EndDate()

    def same_days(self, other: CalendarEntry) -> bool:
        for name in _WEEKDAY_NAMES + ["on_holidays"]:
            if getattr(self, name) == getattr(other, name):
                continue
            return False
        return True

    def __eq__(self, other: CalendarEntry):
        return self.same_days(other) and self.annotations == other.annotations


class Calendar(BaseContainer):
    entries: list[CalendarEntry]

    def __init__(self):
        super().__init__("calendar.txt", CalendarEntry)

    def try_add(self, days: list[str], annots: set[str]
                ) -> (CalendarEntry, bool):
        entry = CalendarEntry(annots)
        for day in days:
            # Holidays will be in the calendar_dates.
            if day == "h":
                entry.on_holidays = True
                continue
            setattr(entry, _WEEKDAY_NAMES[int(day)], DayIsActive(True))

        return entry, self._add(entry)

    def _add(self, new_entry: CalendarEntry) -> bool:
        if any(new_entry == entry for entry in self.entries):
            return False
        super()._add(new_entry)
        return True

    def group_by_holiday(self) -> GroupedEntryTuple:
        """ Return tuple of lists, where the first list only contains entries
        which are holidays and the second one only contains non_holidays. """
        return self._group_by(lambda e: e.on_holidays)

    def _group_by(self, filter_func: FilterFunction) -> GroupedEntryTuple:
        """ Returns two lists, where the first one only contains entries that
        make filter_func True and the second one contains all other entries.
        """
        def non_filter_func(entry: CalendarEntry):
            """ Negates the filter_func. """
            return not filter_func(entry)

        return (list(filter(filter_func, self.entries)),
                list(filter(non_filter_func, self.entries)))


_WEEKDAY_NAMES = [field.name for field in fields(CalendarEntry)
                  if field.type == "DayIsActive"]

GroupedEntryTuple: TypeAlias = tuple[list[CalendarEntry], list[CalendarEntry]]
FilterFunction: TypeAlias = Callable[[CalendarEntry], bool]
