""" Provides Location, a wrapper for latitude/longitude. """

from __future__ import annotations

from dataclasses import dataclass
from math import cos, radians
from typing import Any, Generator, Iterator


DISTANCE_IN_M_PER_LAT_DEG: float = 111320


def get_distance_per_lon_deg(lat: float) -> float:
    """ Return the distance a one degree difference in longitude makes.

    The distance per degree depends on the latitude.
    """
    return DISTANCE_IN_M_PER_LAT_DEG * abs(cos(radians(lat)))


@dataclass
class Location:
    """ The coordinates in degrees latitude/longitude. """
    lat: float
    lon: float

    def __init__(self, lat: Any, lon: Any) -> None:
        self.lat = lat
        self.lon = lon

    @property
    def lat(self) -> float:
        """ The latitude of the location. """
        return self._lat

    @lat.setter
    def lat(self, value: Any) -> None:
        self._lat = self._clean_value(value)

    @property
    def lon(self) -> float:
        """ The longitude of the location. """
        return self._lon

    @lon.setter
    def lon(self, value: Any) -> None:
        self._lon = self._clean_value(value)

    @staticmethod
    def _clean_value(value: Any) -> float:
        """ Ensure the value is of the right type and within the bounds. """
        try:
            value = float(value)
        except (ValueError, TypeError):
            return 0
        # Coordinates are between -90 and 90 degree.
        if -90 > value > 90:
            return 0
        return round(value, 5)

    @property
    def is_valid(self) -> bool:
        """ Return if the location is valid. Invalid locations are at 0, 0. """
        return self.lat != 0 and self.lon != 0

    def __add__(self, other: Location) -> Location:
        if not isinstance(other, Location):
            raise TypeError(f"Can only add Location to Location, "
                            f"not {type(other)}")
        return Location(self.lat + other.lat, self.lon + other.lon)

    def __sub__(self, other: Location) -> Location:
        if not isinstance(other, Location):
            raise TypeError(f"Can only substract Location from Location, "
                            f"not {type(other)}")
        return Location(self.lat - other.lat, self.lon - other.lon)

    def __str__(self) -> str:
        return f"({self.lat:> 9.5f}, {self.lon:> 9.5f})"

    def __repr__(self) -> str:
        return f"Location{str(self)}"

    def __iter__(self) -> Iterator[float]:
        return iter((self.lat, self.lon))

    def __hash__(self) -> int:
        return hash(f"{self.lat},{self.lon}")

    def distances(self, loc: Location) -> Generator[float, None, None]:
        """ Calculates the distances in lat/lon between the two locations. """
        lat_diff, lon_diff = self - loc
        mid_lat = self.lat + lat_diff
        yield DISTANCE_IN_M_PER_LAT_DEG * lat_diff
        lon_dist = get_distance_per_lon_deg(mid_lat) * lon_diff
        yield lon_dist
