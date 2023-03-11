""" Used by the handler to create the file 'routes.txt'. """

from __future__ import annotations

from dataclasses import dataclass, Field
from enum import IntEnum
from pathlib import Path
from time import strptime
from typing import TYPE_CHECKING

import pandas as pd

from pdf2gtfs.datastructures.gtfs_output import BaseContainer, BaseDataClass


if TYPE_CHECKING:
    from pdf2gtfs.datastructures.timetable.entries import TimeTableEntry


def get_route_type(value: str) -> RouteType | None:
    """ Return the route type, depending on value.

    If value is a string containing a number, return the first RouteType using
    that value as GTFS routetype value. If it is a string, return the
    corresponding RouteType.
    """
    value = value.strip().lower()
    if value.isnumeric():
        for route_type, route_value in ROUTE_TYPE_TO_INT.items():
            if route_value == int(value):
                return route_type
        return None
    for route_type in ROUTE_TYPE_TO_INT:
        if value == str(route_type.name).lower():
            return route_type
    return None


def get_route_type_gtfs_value(route_type: RouteType) -> int:
    """ Return the value used in GTFS for the given routetype. """
    return ROUTE_TYPE_TO_INT[route_type]


class RouteType(IntEnum):
    """ The routetype as described by the gtfs. """
    Tram = 0
    StreetCar = 1
    LightRail = 2
    Subway = 3
    Metro = 4
    Rail = 5
    Bus = 6
    Ferry = 7
    CableTram = 8
    AerialLift = 9
    SuspendedCableCar = 10
    Funicular = 11
    Trolleybus = 12
    Monorail = 13

    def to_output(self) -> str:
        """ Numerical string of the current value. """
        return str(get_route_type_gtfs_value(self))


ROUTE_TYPE_TO_INT = {
    RouteType.Tram: 0, RouteType.StreetCar: 0, RouteType.LightRail: 0,
    RouteType.Subway: 1, RouteType.Metro: 1, RouteType.Rail: 2,
    RouteType.Bus: 3, RouteType.Ferry: 4, RouteType.CableTram: 5,
    RouteType.AerialLift: 6, RouteType.SuspendedCableCar: 6,
    RouteType.Funicular: 7, RouteType.Trolleybus: 11, RouteType.Monorail: 12}


@dataclass
class GTFSRouteEntry(BaseDataClass):
    """ A single route in the 'routes.txt' """
    route_id: str
    agency_id: str
    route_short_name: str
    route_long_name: str
    route_type: RouteType

    def __init__(
            self, agency_id: str, short_name: str, long_name: str,
            route_id: str = None, route_type: RouteType = None) -> None:
        from pdf2gtfs.config import Config

        super().__init__(route_id)
        self.route_id = self.id
        self.agency_id = agency_id
        self.route_long_name = long_name
        self.route_short_name = short_name
        route_type = route_type or get_route_type(Config.gtfs_routetype)
        self.route_type: RouteType = route_type

    def get_field_value(self, field: Field):
        """ Return the value of a given Field. """
        value = super().get_field_value(field)
        if field.type != RouteType:
            return value
        return value.value

    def __eq__(self, other: GTFSRouteEntry):
        return (self.agency_id == other.agency_id and
                self.route_short_name == other.route_short_name and
                self.route_long_name == other.route_long_name)

    @staticmethod
    def from_series(s: pd.Series) -> GTFSRouteEntry:
        """ Creates a new GTFSTrip from the given series. """
        return GTFSRouteEntry(s["agency_id"], s["route_short_name"],
                              s["route_long_name"], s["route_id"],
                              get_route_type(s["route_type"]))


class GTFSRoutes(BaseContainer):
    """ Used to create 'routes.txt'. """

    def __init__(self, path: Path, agency_id: str) -> None:
        super().__init__("routes.txt", GTFSRouteEntry, path)
        self.agency_id: str = agency_id

    def add(self, short_name: str = "", long_name: str = "") -> GTFSRouteEntry:
        """ Create a new entry with the given short_name and long_name. """
        route = GTFSRouteEntry(self.agency_id, short_name, long_name)
        return super()._add(route)

    def get(self, short_name: str, long_name: str) -> GTFSRouteEntry:
        """ Return the route route with the given short_name and long_name.
        If route does not exist, raise a KeyError. """
        route = GTFSRouteEntry(self.agency_id, short_name, long_name)
        route = self._get(route)
        if route is None:
            raise KeyError(f"No route with short_name "
                           f"'{short_name}' and long_name '{long_name}'.")
        return route

    @staticmethod
    def names_from_entry(entry: TimeTableEntry) -> tuple[str, str]:
        """ Get the short_name and long_name from the given entry.

        Ensure the times in the entry are actually parseable.
        """
        from pdf2gtfs.config import Config

        start_stop = None
        end_stop = None

        for stop, time_string in entry.values.items():
            try:
                strptime(time_string, Config.time_format)
            except ValueError:
                continue
            if not start_stop:
                start_stop = stop
                continue
            end_stop = stop

        short_name = entry.route_name
        long_name = f"{start_stop.name}-{end_stop.name}"
        return short_name, long_name

    def add_from_entry(self, entry: TimeTableEntry) -> None:
        """ Add a new route entry using the given entry. """
        short_name, long_name = self.names_from_entry(entry)
        self.add(short_name, long_name)

    def get_from_entry(self, entry: TimeTableEntry) -> GTFSRouteEntry:
        """ Return the route entry with the names taken from entry. """
        return self.get(*self.names_from_entry(entry))
