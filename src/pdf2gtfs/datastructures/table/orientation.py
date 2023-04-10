""" Provides different orientations, defined by two (opposite) directions. """

from __future__ import annotations

from abc import ABC, abstractmethod

from pdf2gtfs.datastructures.table.direction import Direction, E, N, S, W


class Orientation(ABC):
    """ Reperesents the orientation of a line using two directions. """
    def __init__(self, name: str, lower: Direction, upper: Direction) -> None:
        self.name = name
        self.lower = lower
        self.upper = upper

    @property
    @abstractmethod
    def normal(self) -> Orientation:
        """ The orientation, that is normal to this orientation.

        This should be symmetric, meaning `o.normal.normal == o`.
        """

    def __repr__(self) -> str:
        return (f"<{self.name}, {repr(self.lower)}, {repr(self.upper)}, "
                f"{id(self)}>")


class _V(Orientation):
    """ Vertical orientation. Used for columns. """
    def __init__(self) -> None:
        super().__init__("V", N, S)

    @property
    def normal(self) -> Orientation:
        return H


class _H(Orientation):
    """ Horizontal orientation. Used for rows. """
    def __init__(self) -> None:
        super().__init__("H", W, E)

    @property
    def normal(self) -> Orientation:
        return V


V = _V()
H = _H()
