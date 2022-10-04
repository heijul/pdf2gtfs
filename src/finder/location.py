""" Provides Location, which is used as a wrapper for latitude/longitude tuples. """

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator


@dataclass(frozen=True)
class Location:
    """ The coordinates in degrees latitude/longitude. """
    lat: float
    lon: float

    def __add__(self, other: Location) -> Location:
        if not isinstance(other, Location):
            raise TypeError(f"Can only add Location to Location, "
                            f"not {type(other)}")
        return Location(self.lat + other.lat, self.lon + other.lon)

    def __str__(self) -> str:
        return f"({self.lat:> 9.5f}, {self.lon:> 9.5f})"

    def __repr__(self) -> str:
        return f"Location{str(self)}"

    def __iter__(self) -> Iterator[float]:
        return iter((self.lat, self.lon))

    def __hash__(self) -> int:
        return hash(f"{self.lat},{self.lon}")
