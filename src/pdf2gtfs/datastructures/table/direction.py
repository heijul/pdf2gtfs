""" Provides the four cardinal directions and the two resulting orientations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class Direction(ABC):
    """ Represents a direction for the Table and Cells.

    The private attribute names (starting with 'p_') are the ones used
    when getting/setting a property of the Table.
    """

    __count = 0

    def __init__(self, name: str, coordinate: str, attr: str, end: str
                 ) -> None:
        assert name == self.__class__.__name__[1]
        assert coordinate in ["x0", "x1", "y0", "y1"]

        self.name = name
        self._coordinate = coordinate
        self._attr = attr
        self._end = end
        # Only four cardinal directions exist.
        Direction.__count += 1
        if Direction.__count > 4:
            raise AssertionError("There should only be four directions.")

    @property
    def coordinate(self) -> str:
        """ The bbox coordinate of this direction. Used in the Bounds. """
        return self._coordinate

    @property
    def attr(self) -> str:
        """ The attribute name of this direction. Used in the Cells. """
        return self._attr

    @property
    def p_attr(self) -> str:
        """ The private attribute name of this direction. """
        return "_" + self.attr

    @property
    def end(self) -> str:
        """ The attribute name of the last element. Used in the Table. """
        return self._end

    @property
    def p_end(self) -> str:
        """ The private attribute name of the last element. """
        return "_" + self.end

    @property
    @abstractmethod
    def o(self) -> Orientation:
        """ The obvious orientation this direction is part of. """

    @property
    @abstractmethod
    def opposite(self) -> Direction:
        """ The direction opposite to this one.

        This should be symmetric, meaning `d.opposite.opposite == d`.
        """

    @property
    def normal_eqivalent(self) -> Direction:
        """ The normal equivalent of this Direction.

        This means the lower Direction of self's Orientation's normal
        if self is the lower Direction of its Orientation, and vice versa.
        """
        if self == self.o.lower:
            return self.o.normal.lower
        return self.o.normal.upper

    def __repr__(self) -> str:
        return f"<{self.name}>"


class _N(Direction):
    def __init__(self) -> None:
        super().__init__("N", "y0", "above", "top")

    @property
    def o(self) -> Orientation:
        return V

    @property
    def opposite(self) -> Direction:
        return S


class _S(Direction):
    def __init__(self) -> None:
        super().__init__("S", "y1", "below", "bot")

    @property
    def o(self) -> Orientation:
        return V

    @property
    def opposite(self) -> Direction:
        return N


class _W(Direction):
    def __init__(self) -> None:
        super().__init__("W", "x0", "prev", "left")

    @property
    def o(self) -> Orientation:
        return H

    @property
    def opposite(self) -> Direction:
        return E


class _E(Direction):
    def __init__(self) -> None:
        super().__init__("E", "x1", "next", "right")

    @property
    def o(self) -> Orientation:
        return H

    @property
    def opposite(self) -> Direction:
        return W


N = _N()
S = _S()
W = _W()
E = _E()
# A tuple of all Directions. Using a tuple allows us to use it as default arg.
D = (N, W, S, E)


class Orientation(ABC):
    """ Represents the orientation of objects using opposite directions. """

    __count = 0

    def __init__(self, name: str, lower: Direction, upper: Direction) -> None:
        assert name == self.__class__.__name__[1]

        self.name = name
        self.lower = lower
        self.upper = upper
        # Only two major orientations exist.
        Orientation.__count += 1
        if Orientation.__count > 2:
            raise AssertionError("There should only be two orientations.")

    @property
    def overlap_func(self) -> str:
        """ The default overlap function used, when using this orientation. """
        return f"is_{self.name.lower()}_overlap"

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
