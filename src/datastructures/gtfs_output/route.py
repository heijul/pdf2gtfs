from __future__ import annotations

from dataclasses import dataclass, Field
from enum import Enum
from typing import Optional, TYPE_CHECKING

import config
from datastructures.gtfs_output import BaseContainer, BaseDataClass


if TYPE_CHECKING:
    from datastructures.timetable.entries import TimeTableEntry


class RouteType(Enum):
    Tram = 0
    StreetCar = 0
    LightRail = 0
    Subway = 1
    Metro = 1
    Rail = 2
    Bus = 3
    Ferry = 4
    CableTram = 5
    AerialLift = 6
    SuspendedCableCar = 6
    Funicular = 7
    Trolleybus = 11
    Monorail = 12

    def to_output(self) -> str:
        return str(self.value)


@dataclass
class Route(BaseDataClass):
    route_id: str
    agency_id: str
    route_short_name: str
    route_long_name: str
    route_type: RouteType

    def __init__(
            self, agency_id: str, short_name: str, long_name: str) -> None:
        super().__init__()
        self.route_id = self.id
        self.agency_id = agency_id
        self.route_long_name = long_name
        self.route_short_name = short_name
        self.route_type: RouteType = config.Config.gtfs_routetype

    def get_field_value(self, field: Field):
        value = super().get_field_value(field)
        if field.type != RouteType:
            return value
        return value.value

    def __eq__(self, other: Route):
        return (self.agency_id == other.agency_id and
                self.route_short_name == other.route_short_name and
                self.route_long_name == other.route_long_name)


class Routes(BaseContainer):
    def __init__(self, agency_id: str) -> None:
        super().__init__("routes.txt", Route)
        self.agency_id: str = agency_id

    def add(self, *, short_name: str = "", long_name: str = "") -> Route:
        route = Route(self.agency_id, short_name, long_name)
        return super()._add(route)

    def get(self, short_name: str, long_name: str) -> Optional[Route]:
        route = Route(self.agency_id, short_name, long_name)
        return self._get(route)

    @staticmethod
    def names_from_entry(entry: TimeTableEntry) -> tuple[str, str]:
        short_name = entry.route_name
        start_name = list(entry.values.keys())[0].name
        end_name = list(entry.values.keys())[-1].name
        long_name = f"{start_name}-{end_name}"
        return short_name, long_name

    def add_from_entry(self, entry: TimeTableEntry) -> None:
        short_name, long_name = self.names_from_entry(entry)
        self.add(short_name=short_name, long_name=long_name)

    def get_from_entry(self, entry: TimeTableEntry) -> Route:
        return self.get(*self.names_from_entry(entry))
