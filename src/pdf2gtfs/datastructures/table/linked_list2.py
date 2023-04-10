""" The LinkedLists used as base classes for Table, Field, Row and Col. """

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import (
    Generator, Generic, Iterator, Optional, Type, TypeAlias, TypeVar)

from pdf2gtfs.datastructures.pdftable.bbox import BBox


logger = logging.getLogger(__name__)

# QuadNode bound
QN = TypeVar("QN", bound="QuadNode")
OQN = TypeVar("OQN", bound=Optional["QuadNode"])
QLL = TypeVar("QLL", bound="QuadLinkedList")
OQLL: TypeAlias = Optional[QLL]


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
    def __init__(self, name: str) -> None:
        super().__init__(name, "above", "top")

    @property
    def default_orientation(self) -> Orientation:
        return V

    @property
    def opposite(self) -> Direction:
        return S


class _S(Direction):
    def __init__(self, name: str) -> None:
        super().__init__(name, "below", "bot")

    @property
    def default_orientation(self) -> Orientation:
        return V

    @property
    def opposite(self) -> Direction:
        return N


class _W(Direction):
    def __init__(self, name: str) -> None:
        super().__init__(name, "prev", "left")

    @property
    def default_orientation(self) -> Orientation:
        return H

    @property
    def opposite(self) -> Direction:
        return E


class _E(Direction):
    def __init__(self, name: str) -> None:
        super().__init__(name, "next", "right")

    @property
    def default_orientation(self) -> Orientation:
        return H

    @property
    def opposite(self) -> Direction:
        return W


N = _N("N")
S = _S("S")
W = _W("W")
E = _E("E")


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


class QuadLinkedList(Generic[QN, OQN]):
    """ Cross between two doubly linked lists. """
    def __init__(self, first_node: QN, last_node: QN) -> None:
        self.bboxes: dict[int: int] = {}
        self._left = None
        self._right = None
        self._top = None
        self._bot = None
        self._update_end_node(W, first_node)
        self._update_end_node(E, last_node)
        self._update_end_node(N, first_node)
        self._update_end_node(S, last_node)
        # Update qll on all nodes.
        for row_field in self.row(self.top):
            for col_field in self.col(row_field):
                col_field.qll = self

    @property
    def left(self) -> OQN:
        """ One of the nodes in the left-most column. """
        return self._get_end_node(d=W)

    @left.setter
    def left(self, node: OQN) -> None:
        self._set_end_node(d=W, node=node)

    @property
    def right(self) -> OQN:
        """ One of the nodes in the right-most column. """
        return self._get_end_node(d=E)

    @right.setter
    def right(self, node: OQN) -> None:
        self._set_end_node(d=E, node=node)

    @property
    def top(self) -> OQN:
        """ One of the nodes in the top row. """
        return self._get_end_node(d=N)

    @top.setter
    def top(self, node: OQN) -> None:
        self._set_end_node(d=N, node=node)

    @property
    def bot(self) -> OQN:
        """ One of the nodes in the bottom column. """
        return self._get_end_node(d=S)

    @bot.setter
    def bot(self, node: OQN) -> None:
        self._set_end_node(d=S, node=node)

    def _get_saved_node(self, d_attr: str) -> OQN:
        """ Some nodes are stored explicitely in the List (e.g. first/last).
        This method can be used to get them without adding explicit type hints.

        :param d_attr: The attribute name the node is stored at.
         Usually this should be a property of one of the directions.
        :return: The node that was stored at the given attribute.
        """
        return getattr(self, d_attr)

    def _get_end_node(self, d: Direction, *, node: OQN = None) -> OQN:
        """ Return one of the end nodes in the given direction.

        :param d: The direction to look for the end node in.
        """
        if node is None:
            node: OQN = self._get_saved_node(d.p_end)
        if not node.get_neighbor(d):
            return node
        self._update_end_node(d)
        return self._get_end_node(d)

    def _set_end_node(self, d: Direction, node: OQN) -> None:
        """ Store the last node in the given direction to node.

        This will fail if node has a neighbor in the given direction.

        :param d: The direction, which specifies, where to store the node.
        :param node: The node to be stored.
        """
        assert node.get_neighbor(d) is None
        setattr(self, d.p_end, node)

    def _update_end_node(self, d: Direction, node: QN = None) -> None:
        """ Update the end node in the given direction to the farthest/last
        node in that direction.

        :param d: The direction to look for the last node.
        """
        if node is None:
            node = self._get_saved_node(d.p_end)
        while node:
            neighbor = node.get_neighbor(d)
            if not neighbor:
                self._set_end_node(d, node)
                break
            node = neighbor

    def get_list(self, o: Orientation, node: OQN = None) -> list[QN]:
        """ Return the full list of nodes in the given orientation.

        :param o: The orientation the nodes will be in.
        :param node: The node used to get a specific row/column. If set to
         None, the first/top node will be used instead.
        """
        if not node:
            node = self._get_end_node(o.lower)
        if not node:
            # TODO NOW: This should not happen? Unless the QLL is empty.
            raise
        # Go to the first node in the list in the given orientation.
        while True:
            neighbor = node.get_neighbor(o.lower)
            if not neighbor:
                break
            node = neighbor
        # Get all nodes in the given orientation.
        nodes: list[QN] = []
        while True:
            nodes.append(node)
            neighbor = node.get_neighbor(o.upper)
            if not neighbor:
                return nodes
            node = neighbor

    @classmethod
    def from_objects(cls: Type[QLL], o: Orientation, nodes: list[QN]) -> QLL:
        """ Create a new QuadLinkedList, which contains all

        :param o: The orientation with which to align the nodes.
        :param nodes: A single row/col of nodes.
        :return: A valid QuadLinkedList containing the nodes.
        """
        # Ensure the objects we have are the first row/col.
        # This is not strictly necessary, but makes bugs more apparent.
        for node in nodes:
            assert node.get_neighbor(o.normal.lower) is None
        # Link nodes using the orientation's upper direction.
        first_node = nodes[0]
        current = first_node
        for node in nodes[1:]:
            node.set_neighbor(o.upper, current)
            current = node
        return cls(first_node, current)

    def insert(self, d: Direction, rel_node: OQN, new_node: QN) -> None:
        """ Inserts the node relative to the rel_node in the given direction.

        :param d: The relative direction of node to rel_node, after insertion.
        :param rel_node: Either a node or None. If node, insertion happens
         adjacent to it. If None, insert as the last node in d.
        :param new_node: The node that will be inserted.
        """
        o = d.default_orientation
        normal = o.normal

        # Ensure the nodes do not have any neighbors in the normal orientation.
        # TODO NOW: This will prevent merging of two QLLs.
        assert new_node.qll
        new_nodes: list[QN] = new_node.qll.get_list(normal)
        for node in new_nodes:
            assert node.has_neighbors(o=normal)
        # If we want to insert a column (i.e. vertical) at the beginning/end,
        # we need a row (i.e. horizontal) to get the first/last column.
        if rel_node is None:
            rel_node = self._get_end_node(normal.lower)
        rel_nodes = self.get_list(normal, rel_node)

        # Strict, to ensure the same number of nodes.
        for rel_node, new_node in zip(rel_nodes, new_nodes, strict=True):
            rel_node.set_neighbor(d, new_node)
            new_node.qll = self

    def row(self, node: QN) -> Generator[QN]:
        """ The row the node resides in.

        :param node: The node in question.
        :return: A generator that yields all objects in the node's row.
        """
        return self.iter(E, node)

    def col(self, node: QN) -> Generator[QN]:
        """ The col the node resides in.

        :param node: The node in question.
        :return: A generator that yields all objects in the node's col.
        """
        return self.iter(S, node)

    def get_bbox_of(self, nodes: Iterator[QN]) -> BBox:
        """ Return the combined bbox of nodes.

        Also caches the results, in case the same bbox is requested again.

        :param nodes: The nodes to get the bbox from.
        :return: A bbox, that contains all the nodes' bboxes.
        """
        from pdf2gtfs.datastructures.table.fields2 import EmptyField

        bboxes = [node.bbox for node in nodes
                  if not isinstance(node, EmptyField)]
        # No need to cache a single bbox.
        if len(bboxes) == 1:
            return bboxes[0]
        # If a bboxes' coordinates change, its hash changes as well.
        nodes_hashes = sorted(map(hash, bboxes))
        nodes_hash = hash("".join(map(str, nodes_hashes)))
        if nodes_hash not in self.bboxes:
            self.bboxes[nodes_hash] = BBox.from_bboxes(bboxes)
        return self.bboxes[nodes_hash]

    def iter(self, d: Direction, node: OQN = None) -> Generator[QN]:
        """ Start on the opposite end of d and iterate over nodes towards d.

        :param d: The direction to iterate towards to.
        :param node: If given, the generator will yield nodes of the
            col/row of node, based on d. Otherwise, always yield the
            first col/row.
        :return: An iterator over the nodes.
        """
        node = self._get_end_node(d.opposite, node=node)
        while node:
            yield node
            node = node.get_neighbor(d)
