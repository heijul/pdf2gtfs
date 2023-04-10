from __future__ import annotations

from typing import Generator, Generic, Optional, TypeVar

from pdf2gtfs.datastructures.table.direction import Direction, E, N, S, W
from pdf2gtfs.datastructures.table.quadlinkedlist import OQLL
from pdf2gtfs.datastructures.table.orientation import Orientation


QN = TypeVar("QN", bound="QuadNode")
OQN = TypeVar("OQN", bound=Optional["QuadNode"])


class QuadNode(Generic[QN, OQN]):
    """ A single quadnode. Hold references to all its adjacent neighbors. """

    def __init__(self, *args, **kwargs) -> None:
        self._list = None
        self._prev = None
        self._next = None
        self._above = None
        self._below = None
        super().__init__(*args, **kwargs)

    @property
    def prev(self) -> OQN:
        return self.get_neighbor(W)

    @prev.setter
    def prev(self, node: OQN) -> None:
        self.set_neighbor(W, node)

    @property
    def next(self) -> OQN:
        return self.get_neighbor(E)

    @next.setter
    def next(self, node: OQN) -> None:
        self.set_neighbor(E, node)

    @property
    def above(self) -> OQN:
        return self.get_neighbor(N)

    @above.setter
    def above(self, node: OQN) -> None:
        self.set_neighbor(N, node)

    @property
    def below(self) -> OQN:
        return self.get_neighbor(S)

    @below.setter
    def below(self, node: OQN) -> None:
        self.set_neighbor(S, node)

    def get_neighbor(self, d: Direction) -> OQN:
        """ Get the next neighbor in one of the four directions.

        :param d: The direction.
        :return: This nodes next neighbor in the given direction.
        """
        return getattr(self, d.p_attr)

    def set_neighbor(self, d: Direction, neighbor: OQN) -> None:
        current_neighbor: OQN = self.get_neighbor(d)
        if not neighbor:
            setattr(self, d.p_attr, None)
            if current_neighbor:
                setattr(current_neighbor, d.opposite.p_attr, None)
            return

        setattr(self, d.p_attr, neighbor)
        setattr(neighbor, d.opposite.p_attr, self)
        neighbor.qll = self.qll
        if current_neighbor:
            setattr(neighbor, d.p_attr, current_neighbor)
            setattr(current_neighbor, d.opposite.p_attr, neighbor)

    def set_neighbor2(self, d: Direction, neighbor: OQN) -> None:
        """ Set the neighbor in direction d to value.

        If the current node already has a neighbor N in the given direction,
        N will be accessible by using e.g. value.get_neighbor(d) afterwards.

        :param d: Will update the next neighbor in this direction.
        :param neighbor: Either a node or None.
        """
        current_neighbor: OQN = self.get_neighbor(d)
        # We need to remove the neighbor first, to prevent it to try to
        # update ourselves.
        if current_neighbor:
            setattr(current_neighbor, d.opposite.p_attr, None)
        if not neighbor:
            setattr(self, d.p_attr, None)
            return
        # If we want to insert a neighbor in a direction, when the neighbor
        # already has another neighbor in the opposite direction,
        # we don't know which comes first.
        # For example: B1 <-> C, A <-> B2 => B2.set_neighbor(E, B)
        # Here we don't know if B1 should come before A or vice versa.
        if self.get_neighbor(d.opposite) not in [None, self]:
            assert neighbor.get_neighbor(d.opposite) in [None, self]
        # In the same way as above. Given A <-> B1, B2 <-> C, we can not do
        # A.set_neighbor(E, B2), because it iss unclear, which of
        # B1 and C comes first.
        if current_neighbor:
            assert neighbor.get_neighbor(d) in [None, self]

        # Set _prev/_next/_above/_below.
        setattr(self, d.p_attr, neighbor)
        if neighbor.get_neighbor(d.opposite) != self:
            neighbor.set_neighbor(d.opposite, self)
        if not current_neighbor:
            return
        neighbor.set_neighbor(d, current_neighbor)

    def has_neighbors(self, *, d: Direction = None, o: Orientation = None
                      ) -> bool:
        """ Whether the node has any neighbors in the direction/orientation.

        Only exactly one of d/o can be given at a time.
        :param d: The direction to check for neighbors in.
        :param o: The orientation. Simply checks both directions of o.
        :return: True if there exist any neighbors, False otherwise.
        """
        # Exactly one of d/o is required.
        assert d is None or o is None
        assert d is not None or o is not None
        if o:
            return (self.has_neighbors(d=o.lower) or
                    self.has_neighbors(d=o.upper))
        return self.get_neighbor(d) is not None

    @property
    def qll(self) -> OQLL:
        """ The QuadLinkedList, this node belongs to, if any. """
        return self._list

    @qll.setter
    def qll(self, quad_linked_list: OQLL) -> None:
        self._list = quad_linked_list

    def iter_col(self) -> Generator[QN]:
        f = self
        while f:
            yield f
            f = f.below

    def iter(self, d: Direction) -> Generator[QN]:
        field = self
        while field:
            yield field
            field = field.get_neighbor(d)
