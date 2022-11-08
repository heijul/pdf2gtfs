""" Used by the handler to create the file 'calendar.txt'. """

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, fields
from typing import Callable, Optional, TypeAlias

from config import Config
from datastructures.gtfs_output import BaseContainer, BaseDataClass, str_wrap


@dataclass
class DayIsActive:
    """ Simple dataclass used by calendar entries, to turn booleans
    (i.e. service is active on day X) into numeric strings. """
    active: bool = True

    def __eq__(self, other: DayIsActive) -> bool:
        return self.active == other.active

    def to_output(self) -> str:
        """ Returns '1' or '0' based on self.active """
        return str(int(self.active))

    def __repr__(self) -> str:
        return self.to_output()


class ServiceDay:
    """ Service day as defined by the gtfs (can have morethan 24 hours). """

    def __init__(self, date: dt.date):
        self.date = date

    def to_output(self) -> str:
        """ ISO-8601 formatted date. """
        return str_wrap(self.date.strftime("%Y%m%d"))

    def __eq__(self, other: ServiceDay):
        return self.date == other.date

    def __repr__(self) -> str:
        return self.to_output()


class StartDate(ServiceDay):
    """ The start date. Will be set to the first of the current years,
    if the configuration was not changed. """

    def __init__(self) -> None:
        super().__init__(Config.gtfs_date_bounds[0])


class EndDate(ServiceDay):
    """ The end date. Will be set to the last of the current years,
    if the configuration was not changed. """

    def __init__(self) -> None:
        super().__init__(Config.gtfs_date_bounds[1])


@dataclass(init=False)
class GTFSCalendarEntry(BaseDataClass):
    """ A single entry in the calendar file. """
    service_id: str
    monday: DayIsActive = DayIsActive(False)
    tuesday: DayIsActive = DayIsActive(False)
    wednesday: DayIsActive = DayIsActive(False)
    thursday: DayIsActive = DayIsActive(False)
    friday: DayIsActive = DayIsActive(False)
    saturday: DayIsActive = DayIsActive(False)
    sunday: DayIsActive = DayIsActive(False)
    start_date: ServiceDay = StartDate()
    end_date: ServiceDay = EndDate()

    def __init__(self, days: list[str] = None, annots: set[str] | None = None):
        super().__init__()
        self.service_id = self.id
        self.on_holidays = False
        self.start_date = StartDate()
        self.end_date = EndDate()
        self._set_days(days)
        self._set_annotations(annots)

    def _set_days(self, days: Optional[list[str]]) -> None:
        if not days:
            return
        for day in days:
            # Holidays will be in the calendar_dates.
            if day == "h":
                self.on_holidays = True
                continue
            setattr(self, WEEKDAY_NAMES[int(day)], DayIsActive(True))

    def _set_annotations(self, annots: Optional[set[str]]) -> None:
        self.annotations = annots or set()

    def same_days(self, other: GTFSCalendarEntry) -> bool:
        """ Check if other and self are active on the same days. """
        for name in WEEKDAY_NAMES + ["on_holidays"]:
            if getattr(self, name) == getattr(other, name):
                continue
            return False
        return True

    def disable(self) -> None:
        """ No service day will be active, after this is run. """
        for name in WEEKDAY_NAMES:
            setattr(self, name, DayIsActive(False))

    def __eq__(self, other: GTFSCalendarEntry):
        return self.same_days(other) and self.annotations == other.annotations


class GTFSCalendar(BaseContainer):
    """ Used to create 'calendar.txt'. """

    entries: list[GTFSCalendarEntry]

    def __init__(self) -> None:
        super().__init__("calendar.txt", GTFSCalendarEntry)

    def add(self, days: list[str], annots: set[str]) -> GTFSCalendarEntry:
        """ Add an entry, active on the given days with the given annots. """
        entry = GTFSCalendarEntry(days, annots)
        return self._add(entry)

    def get(self, entry: GTFSCalendarEntry) -> GTFSCalendarEntry:
        """ Returns the given entry, if an equal entry does not exist yet,
        otherwise returns the existing_entry. """
        existing_entry = self._get(entry)
        return existing_entry if existing_entry else entry

    def group_by_holiday(self) -> GroupedEntryTuple:
        """ Return tuple of lists, where the first list only contains entries
        which are holidays and the second one only contains non-holidays. """
        return self._group_by(lambda e: e.on_holidays)

    def _group_by(self, filter_func: FilterFunction) -> GroupedEntryTuple:
        """ Returns two lists, where the first one only contains entries that
        make filter_func True and the second one contains all other entries.
        """

        def non_filter_func(entry: GTFSCalendarEntry):
            """ Negates the filter_func. """
            return not filter_func(entry)

        return (list(filter(filter_func, self.entries)),
                list(filter(non_filter_func, self.entries)))

    def get_with_annot(self, annotation) -> list[GTFSCalendarEntry]:
        """ Return all entries, that have the given annotation. """
        return [e for e in self.entries if annotation in e.annotations]

    def get_annotations(self) -> list[str]:
        """ Return all annotations. """
        annot_set = set()
        raw_annots = [e.annotations for e in self.entries]
        for _annot in raw_annots:
            annot_set |= _annot
        return sorted(annot_set)


WEEKDAY_NAMES = [field.name for field in fields(GTFSCalendarEntry)
                 if field.type == "DayIsActive"]

GroupedEntryTuple: TypeAlias = (
    tuple[list[GTFSCalendarEntry], list[GTFSCalendarEntry]])
FilterFunction: TypeAlias = Callable[[GTFSCalendarEntry], bool]
