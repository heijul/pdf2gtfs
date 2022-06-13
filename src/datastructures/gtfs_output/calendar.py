from __future__ import annotations

from abc import ABC, abstractmethod
import datetime as dt
from dataclasses import fields, dataclass
from typing import TypeAlias, Callable

from datastructures.gtfs_output.base import BaseContainer, BaseDataClass


@dataclass
class DayIsActive:
    active: bool = True

    def __eq__(self, other: DayIsActive) -> bool:
        return self.active == other.active

    def to_output(self) -> str:
        return str(int(self.active))


class ServiceDay(ABC):
    def __init__(self,
                 date: dt.date | None = None, time: dt.date | None = None):
        self.date = date if date else self.default_date
        self.time = time if time else self.default_time

    @property
    @abstractmethod
    def default_date(self):
        pass

    @property
    @abstractmethod
    def default_time(self):
        pass

    @property
    def default_year(self):
        return dt.date.today().year

    def to_output(self) -> str:
        return self.date.strftime("%Y%m%d")

    def __eq__(self, other: ServiceDay):
        return self.date == other.date


class StartDate(ServiceDay):
    @property
    def default_date(self):
        return dt.date(year=self.default_year, month=1, day=1)

    @property
    def default_time(self):
        return dt.time()


class EndDate(ServiceDay):
    @property
    def default_date(self):
        return dt.date(year=self.default_year, month=12, day=31)

    @property
    def default_time(self):
        return None


class DefaultStartDate(StartDate):
    def __init__(self):
        super().__init__()


class DefaultEndDate(EndDate):
    def __init__(self):
        super().__init__()


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
    start_date: ServiceDay = DefaultStartDate
    end_date: ServiceDay = DefaultEndDate

    def __init__(self, annots: set[str] | None = None):
        super().__init__()
        self.service_id = self.id
        self.on_holidays = False
        self.annotations = annots or set()
        self._set_dates()

    def _set_dates(self):
        # TODO: Make configurable
        self.start_date = StartDate()
        self.end_date = EndDate()

    def is_similar_to(self, other: CalendarEntry) -> bool:
        return self.same_dates(other) and self.annotations == other.annotations

    def same_dates(self, other: CalendarEntry) -> bool:
        """ Return if self and other are active on the same dates. """
        if (self.start_date != other.start_date or
                self.end_date != other.end_date):
            return False
        for name in _WEEKDAY_NAMES:
            if getattr(self, name) != getattr(other, name):
                return False
        return self.on_holidays == other.on_holidays


class Calendar(BaseContainer):
    entries: list[CalendarEntry]

    def __init__(self):
        super().__init__("calendar.txt", CalendarEntry)

    def add(self, days: list[str], annots: set[str]) -> (CalendarEntry, bool):
        new_entry = CalendarEntry(annots)
        for day in days:
            # Holidays will be in the calendar_dates.
            if day == "h":
                new_entry.on_holidays = True
                continue
            setattr(new_entry, _WEEKDAY_NAMES[int(day)], DayIsActive(True))

        entry = self.get_existing(new_entry)
        self._add(entry)
        return entry, entry != new_entry

    def _add(self, new_entry: CalendarEntry) -> None:
        if any(new_entry.id == entry.id for entry in self.entries):
            return
        super()._add(new_entry)

    def get_existing(self, new_entry: CalendarEntry) -> CalendarEntry | None:
        """ Return new_entry if no other entry exists with the same dates.
        Otherwise, return the existing entry. """

        for entry in self.entries:
            if entry.is_similar_to(new_entry):
                return entry
        return new_entry

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
