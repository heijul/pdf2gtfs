from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Type, TYPE_CHECKING

import pandas as pd

from utils import get_edit_distance

if TYPE_CHECKING:
    from finder.routes import StopName

# Tolerance in degree. 0.009 ~= 1km
CLOSE_TOLERANCE = 0.009


class TransportType(Enum):
    Station = 1
    Platform = 2
    StopPosition = 3

    def compare(self, other: TransportType) -> int:
        """ -1 if self < other, 0 if self == other, 1 if self > other. """
        return int(self.value > other.value) - int(self.value < other.value)


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

    def __init__(self, name: StopName, *,
                 typ: TransportType = None, location: Location = None,
                 lat: float = 0, lon: float = 0):
        self.type = typ
        self.name = name
        self.location = location if location else Location(lat, lon)
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

    @classmethod
    def from_series(cls: Type[PublicTransport], series: pd.Series):
        obj: cls = cls(series["name"], lat=series["lat"], lon=series["lon"])
        return obj

    def __repr__(self):
        return f"{self.type.name}('{self.stop}', {self.location})"

    def __lt__(self, other: PublicTransport) -> bool:
        # Prefer stations for nodes which are close to each other
        comp = self.type.compare(other.type)
        if self.location.close(other.location):
            if comp == 0:
                return self.name_dist() <= other.name_dist()
            return comp == -1
        # Don't compare name_distance if locations are not close.
        return comp <= 0

    def __le__(self, other: PublicTransport) -> bool:
        return self == other or self < other

    def __eq__(self, other: PublicTransport) -> bool:
        return all((self.type == other.type,
                    self.name == other.name,
                    self.stop == other.stop))


class Station(PublicTransport):
    def __init__(self, name: StopName, *, lat: float, lon: float):
        super().__init__(name, typ=TransportType(1), lat=lat, lon=lon)


class Platform(PublicTransport):
    def __init__(self, name: StopName, lat: float, lon: float):
        super().__init__(name, typ=TransportType(2), lat=lat, lon=lon)


class StopPosition(PublicTransport):
    def __init__(self, name: StopName, lat: float, lon: float):
        super().__init__(name, typ=TransportType(3), lat=lat, lon=lon)


def from_series(series: pd.Series) -> PublicTransport:
    if series["transport"] == "station":
        return Station.from_series(series)
    if series["transport"] == "platform":
        return Platform.from_series(series)
    if series["transport"] == "stop_position":
        return StopPosition.from_series(series)
