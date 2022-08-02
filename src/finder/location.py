from __future__ import annotations

from dataclasses import dataclass

from geopy.distance import distance


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


