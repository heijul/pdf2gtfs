from __future__ import annotations

from dataclasses import dataclass, Field
from enum import Enum

import config
from datastructures.gtfs_output.__init__ import (
    BaseDataClass, BaseContainer)


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
    Funicular = 7
    Trolleybus = 11
    Monorail = 12


@dataclass
class Route(BaseDataClass):
    route_id: int
    route_short_name: str
    route_long_name: str
    route_type: RouteType

    def __init__(self, route_short_name: str, route_long_name: str) -> None:
        super().__init__()
        self.route_id = self.id
        self.route_long_name = route_long_name
        self.route_short_name = route_short_name
        self.route_type: RouteType = RouteType[config.Config.gtfs_routetype]

    def get_field_value(self, field: Field):
        value = super().get_field_value(field)
        if field.type != RouteType:
            return value
        return value.value

    def __eq__(self, other: Route):
        return (self.route_short_name == other.route_short_name and
                self.route_long_name == other.route_long_name)


class Routes(BaseContainer):
    def __init__(self):
        super().__init__("routes.txt", Route)

    def add(self, *, short_name: str = "", long_name: str = "") -> Route:
        route = Route(short_name, long_name)
        if route in self.entries:
            return self.entries[self.entries.index(route)]
        super()._add(route)
        return route
