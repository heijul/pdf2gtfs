""" The base class for Nodes contained in a QuadLinkedList. """

from __future__ import annotations

from typing import Generator, Generic, Optional, TYPE_CHECKING, TypeVar

from pdf2gtfs.datastructures.table.direction import (
    Direction, E, N, Orientation, S, W,
    )

if TYPE_CHECKING:
    from pdf2gtfs.datastructures.table.quadlinkedlist import OQLL


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
        """ The previous node (i.e. left of this one) or None. """
        return self.get_neighbor(W)

    @prev.setter
    def prev(self, node: OQN) -> None:
        self.set_neighbor(W, node)

    @property
    def next(self) -> OQN:
        """ The next node (i.e. right of this one) or None. """
        return self.get_neighbor(E)

    @next.setter
    def next(self, node: OQN) -> None:
        self.set_neighbor(E, node)

    @property
    def above(self) -> OQN:
        """ The node above this one or None. """
        return self.get_neighbor(N)

    @above.setter
    def above(self, node: OQN) -> None:
        self.set_neighbor(N, node)

    @property
    def below(self) -> OQN:
        """ The node below this one or None. """
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
        """ Update the neighbor in the given direction.

        This should _always_ be called from the node the neighbor is moved to.

        If the current node already has a neighbor N in the given direction,
            N will be accessible by using neighbor.get_neighbor(d) afterwards.

        :param d: The direction the neighbor will be placed in.
        :param neighbor: The new neighbor or None.
        """
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

    def iter(self, d: Direction) -> Generator[QN]:
        """ Return an Iterator over the neighbors of this field in the given d.

        This node will always be the first node yielded, i.e. no neighbor in
            the opposite direction of d will be returned.

        :param d:
        """
        field = self
        while field:
            yield field
            field = field.get_neighbor(d)
