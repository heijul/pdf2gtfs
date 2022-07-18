from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from finder.routes import StopName
from utils import get_edit_distance


# Tolerance in degree. 0.009 ~= 1km
CLOSE_TOLERANCE = 0.009


class TransportType(Enum):
    Station: 1
    Platform: 2
    StopPosition: 3


@dataclass
class Location:
    lat: float
    lon: float

    def close(self, other: Location) -> bool:
        return (abs(self.lat - other.lat) <= CLOSE_TOLERANCE and
                abs(self.lon - other.lon) <= CLOSE_TOLERANCE)


class PublicTransport:
    type: TransportType
    name: str
    location: Location

    def __init__(self, typ: TransportType,
                 name: StopName, location: Location):
        self.type = typ
        self.name = name
        self.location = location
        self._stop: Optional[StopName] = None
        self.is_permutation = False

    @property
    def stop(self):
        return self._stop

    def set_stop(self, stop: StopName, is_permutation: bool = False):
        self.is_permutation = is_permutation
        self._stop = stop

    def name_dist(self) -> int:
        if self.stop is None:
            return -1
        if self.is_permutation or self.name.lower() == self.stop.lower():
            return 0
        return get_edit_distance(self.name, self.stop)

    def __gt__(self, other: PublicTransport):
        # Prefer stations for nodes which are close to each other
        if self.location.close(other.location):
            if self.type.value < other.type.value:
                return self
            return (other if self.type > other.type else
                    self if self.name_dist() <= other.name_dist() else other)


class Station:
    def __init__(self, name: StopName, lat: float, lon: float):
        super().__init__(TransportType(1), name, lat, lon)


class Platform:
    def __init__(self, name: StopName, lat: float, lon: float):
        super().__init__(TransportType(2), name, lat, lon)


class StopPosition:
    def __init__(self, name: StopName, lat: float, lon: float):
        super().__init__(TransportType(3), name, lat, lon)
