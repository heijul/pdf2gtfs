""" Provides the four cardinal directions.  """

from __future__ import annotations

from abc import ABC, abstractmethod


class Direction(ABC):
    """ Represents a direction for the linked lists. """
    def __init__(self, name: str, attr: str, end: str) -> None:
        assert name == self.__class__.__name__[1]
        self.name = name
        self._attr = attr
        self._end = end

    @property
    def attr(self) -> str:
        """ The attribute name of the direction. """
        return self._attr

    @property
    def p_attr(self) -> str:
        """ The private attribute name of this direction. """
        return "_" + self.attr

    @property
    def end(self) -> str:
        """ The attribute name of the last element in this direction. """
        return self._end

    @property
    def p_end(self) -> str:
        """
        The private attribute name of the last element in this direction.
        """
        return "_" + self.end

    @property
    @abstractmethod
    def default_orientation(self) -> Orientation:
        """ The obvious orientation, this direction is part of. """

    @property
    @abstractmethod
    def opposite(self) -> Direction:
        """ The direction opposite to this one. """

    def __repr__(self) -> str:
        return f"<{self.name}>"


class _N(Direction):
    def __init__(self) -> None:
        super().__init__("N", "above", "top")

    @property
    def default_orientation(self) -> Orientation:
        return V

    @property
    def opposite(self) -> Direction:
        return S


class _S(Direction):
    def __init__(self) -> None:
        super().__init__("S", "below", "bot")

    @property
    def default_orientation(self) -> Orientation:
        return V

    @property
    def opposite(self) -> Direction:
        return N


class _W(Direction):
    def __init__(self) -> None:
        super().__init__("W", "prev", "left")

    @property
    def default_orientation(self) -> Orientation:
        return H

    @property
    def opposite(self) -> Direction:
        return E


class _E(Direction):
    def __init__(self) -> None:
        super().__init__("E", "next", "right")

    @property
    def default_orientation(self) -> Orientation:
        return H

    @property
    def opposite(self) -> Direction:
        return W


N = _N()
S = _S()
W = _W()
E = _E()


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