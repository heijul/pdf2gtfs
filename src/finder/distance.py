""" Provides comparable objects for distances. """

from __future__ import annotations

from math import cos, radians


class Distance:
    """ Distance between two locations. """

    def __init__(self, *, m: float = None, km: float = None):
        self.distance = abs(m if m is not None else km * 1000)

    @property
    def distance(self) -> float:
        """ The distance in meters. """
        return self._distance

    @distance.setter
    def distance(self, value: float) -> None:
        self._distance = round(value, 0)

    @property
    def m(self) -> float:
        """ The distance in meters. """
        return self.distance

    @property
    def km(self) -> float:
        """ The distance in kilometers. """
        return self.distance / 1000

    def __rmul__(self, other: object) -> Distance:
        if isinstance(other, (float, int)):
            return Distance(m=self.m * other)
        if isinstance(other, Distance):
            return Distance(m=self.m * other.m)
        raise TypeError(f"Can only multiply Distances with Distances or "
                        f"Distances with int/float, not '{type(object)}'.")

    def __mul__(self, other: object) -> Distance:
        return self.__rmul__(other)

    def __add__(self, other: object):
        if isinstance(other, Distance):
            return Distance(m=self.m + other.m)
        raise TypeError(f"Can only add Distances to Distances, "
                        f"not '{type(object)}'.")

    def __truediv__(self, other: object) -> Distance:
        if isinstance(other, Distance):
            return Distance(m=self.m / other.m)
        raise TypeError(f"Can only divide Distances by Distances, "
                        f"not '{type(object)}'.")

    def __sub__(self, other: object) -> Distance:
        if isinstance(other, Distance):
            return Distance(m=self.m - other.m)
        if isinstance(other, (float, int)):
            return Distance(m=self.m - other)
        raise TypeError(f"Can only substract Distances, float and int from "
                        f"Distances, not '{type(object)}'.")

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Distance):
            return False
        return self.distance == other.distance

    def __lt__(self, other: Distance) -> bool:
        if not isinstance(other, Distance):
            raise TypeError(
                f"Can only compare Distance to Distance, not {type(object)}.")
        return self.distance < other.distance

    def __le__(self, other: Distance) -> bool:
        return self == other or self < other

    def __gt__(self, other: Distance) -> bool:
        return not self <= other

    def __ge__(self, other: Distance) -> bool:
        return not self < other

    def __repr__(self) -> str:
        return f"Dist({self.m}m)"


DISTANCE_PER_LAT_DEG = Distance(km=111.32)


def get_distance_per_lon_deg(lat: float) -> Distance:
    """ Return the distance a one degree difference in longitude makes.

    The distance per degree depends on the latitude.
    """
    return DISTANCE_PER_LAT_DEG * abs(cos(radians(lat)))
