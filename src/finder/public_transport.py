from __future__ import annotations

from enum import IntEnum
from typing import Optional, Type

import pandas as pd

from finder.location import Location
from finder.types import StopName
from utils import get_edit_distance, replace_abbreviations


class TransportType(IntEnum):
    ExistingTransportType = 0
    Station = 1
    Platform = 2
    StopPosition = 3
    Dummy = 4

    def compare(self, other: TransportType) -> int:
        """ -1 if self < other, 0 if self == other, 1 if self > other. """
        return int(self.value > other.value) - int(self.value < other.value)

    @staticmethod
    def get(name: str) -> TransportType:
        name = name.lower().replace(" ", "")
        if name == "station":
            return TransportType.Station
        if name == "platform":
            return TransportType.Platform
        if name == "stop_position":
            return TransportType.StopPosition


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
    def stop(self) -> StopName:
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

    def __repr__(self) -> str:
        if not self.stop:
            return f"{self.type.name}('{self.name}', {self.location})"
        return (f"{self.type.name}('{self.stop}', "
                f"'{self.name}', {self.location})")

    def __lt__(self, other: PublicTransport) -> bool:
        # Prefer lower TransportType for nodes which are close to each other
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


class ExistingTransport(PublicTransport):
    def __init__(self, name: StopName, lat: float, lon: float) -> None:
        super().__init__(name, typ=TransportType(0), lat=lat, lon=lon)


class Station(PublicTransport):
    def __init__(self, name: StopName, *, lat: float, lon: float):
        super().__init__(name, typ=TransportType(1), lat=lat, lon=lon)


class Platform(PublicTransport):
    def __init__(self, name: StopName, lat: float, lon: float):
        super().__init__(name, typ=TransportType(2), lat=lat, lon=lon)


class StopPosition(PublicTransport):
    def __init__(self, name: StopName, lat: float, lon: float):
        super().__init__(name, typ=TransportType(3), lat=lat, lon=lon)


class DummyTransport(PublicTransport):
    def __init__(self, name: StopName):
        super().__init__(name, typ=TransportType(4), lat=-1, lon=-1)


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
