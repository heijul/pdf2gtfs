from abc import ABC, abstractmethod
import datetime as dt
from dataclasses import dataclass

from config import Config


@dataclass
class DayIsActive:
    active: bool = True


class ServiceDay(ABC):
    def __init__(self, date, time):
        self.date = date if date else self.default_date
        self.time = time if time else self.default_time

    @property
    def default_year(self):
        return dt.date.today().year

    @abstractmethod
    @property
    def default_date(self):
        pass

    @abstractmethod
    @property
    def default_time(self):
        pass


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


class Calendar:
    id: int
    mon: DayIsActive
    tue: DayIsActive
    wed: DayIsActive
    thu: DayIsActive
    fri: DayIsActive
    sat: DayIsActive
    sun: DayIsActive
    start_date: ServiceDay
    end_date: ServiceDay

    def __init__(self):
        self._set_dates()

    def _set_dates(self):
        self.start_date = ServiceDay(*Config.get_if_set("start_date"))
