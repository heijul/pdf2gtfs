from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Type

import pandas as pd
from geopy.distance import distance

from utils import get_edit_distance, replace_abbreviations
from finder.types import StopName


class TransportType(Enum):
    Station = 1
    Platform = 2
    StopPosition = 3

    def compare(self, other: TransportType) -> int:
        """ -1 if self < other, 0 if self == other, 1 if self > other. """
        return int(self.value > other.value) - int(self.value < other.value)


@dataclass(frozen=True)
class Location:
    lat: float
    lon: float

    def distance(self, other: Location) -> float:
        """ Return distance between two locations in km. """
        return distance(tuple(self), tuple(other)).km

    def close(self, other: Location) -> bool:
        return self.distance(other) <= 1

    def __str__(self):
        return f"({self.lat:.4f}, {self.lon:.4f})"

    def __iter__(self):
        return iter((self.lat, self.lon))


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
        name = replace_abbreviations(self.name).casefold().lower()
        stop = replace_abbreviations(self.stop).casefold().lower()
        if self.is_permutation or name == stop:
            return 0
        return get_edit_distance(name, stop)

    @classmethod
    def from_series(cls: Type[PublicTransport], series: pd.Series):
        obj: cls = cls(series["name"], lat=series["lat"], lon=series["lon"])
        return obj

    def __repr__(self):
        if not self.stop:
            return f"{self.type.name}('{self.name}', {self.location})"
        return (f"{self.type.name}('{self.stop}', "
                f"'{self.name}', {self.location})")

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


def from_series(series: pd.Series, stop: StopName = "") -> PublicTransport:
    if series["transport"] == "station":
        transport = Station.from_series(series)
    elif series["transport"] == "platform":
        transport = Platform.from_series(series)
    else:
        transport = StopPosition.from_series(series)
    if stop:
        transport.set_stop(stop)
    return transport
