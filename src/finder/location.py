from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

from geopy.distance import distance

from config import Config


@dataclass(frozen=True)
class Location:
    lat: float
    lon: float

    def distance(self, other: Location) -> float:
        """ Return distance between two locations in m. """
        return distance(tuple(self), tuple(other)).m

    def close(self, other: Location) -> bool:
        return self.distance(other) <= Config.cluster_radius

    def __str__(self) -> str:
        return f"({self.lat:.5f}, {self.lon:.5f})"

    def __repr__(self) -> str:
        return f"Location{str(self)}"

    def __iter__(self) -> Iterator[float]:
        return iter((self.lat, self.lon))

    def valid(self) -> bool:
        # TODO: Change existing nodes to use None instead of -1???
        return self.lat is not None and self.lon is not None
