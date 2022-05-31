from abc import ABC, abstractmethod
import datetime as dt
from dataclasses import fields, dataclass

from datastructures.gtfs_output.basestructures import BaseContainer, BaseDataClass


@dataclass
class DayIsActive:
    active: bool = True

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

    def __init__(self):
        super().__init__()
        self.service_id = self.id
        self._set_dates()

    def _set_dates(self):
        # TODO: Make configurable
        self.start_date = StartDate()
        self.end_date = EndDate()


class Calendar(BaseContainer):
    def __init__(self):
        super().__init__("calendar.txt", CalendarEntry)

    def add(self, days: list[str]) -> CalendarEntry:
        entry = CalendarEntry()
        weekday_names = [f.name for f in fields(entry)
                         if f.type == DayIsActive]
        for day in days:
            # Holidays will be in the calendar_dates.
            if day == "h":
                continue
            setattr(entry, weekday_names[int(day)], DayIsActive(True))

        self._add(entry)
        return entry
