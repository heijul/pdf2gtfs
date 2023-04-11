""" The LinkedLists used as base classes for Table, Field, Row and Col. """

from __future__ import annotations

from typing import (
    Generator, Generic, Iterator, Optional, Type, TypeAlias, TypeVar,
    )

from pdf2gtfs.datastructures.pdftable.bbox import BBox
from pdf2gtfs.datastructures.table.direction import (
    Direction, E, N, Orientation, S, W,
    )

from pdf2gtfs.datastructures.table.nodes import OQN, QN


QLL = TypeVar("QLL", bound="QuadLinkedList")
OQLL: TypeAlias = Optional[QLL]


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
        return self.get_end_node(d=W)

    @left.setter
    def left(self, node: OQN) -> None:
        self._set_end_node(d=W, node=node)

    @property
    def right(self) -> OQN:
        """ One of the nodes in the right-most column. """
        return self.get_end_node(d=E)

    @right.setter
    def right(self, node: OQN) -> None:
        self._set_end_node(d=E, node=node)

    @property
    def top(self) -> OQN:
        """ One of the nodes in the top row. """
        return self.get_end_node(d=N)

    @top.setter
    def top(self, node: OQN) -> None:
        self._set_end_node(d=N, node=node)

    @property
    def bot(self) -> OQN:
        """ One of the nodes in the bottom column. """
        return self.get_end_node(d=S)

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

    def get_end_node(self, d: Direction, *, node: OQN = None) -> OQN:
        """ Return one of the end nodes in the given direction.

        :param d: The direction to look for the end node in.
        """
        if node is None:
            node: OQN = self._get_saved_node(d.p_end)
        if not node.get_neighbor(d):
            return node
        self._update_end_node(d, node)
        return self.get_end_node(d)

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
            node = self.get_end_node(o.lower)
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

        # TODO NOW: Check that each new_node only has neighbors,
        #  that are in new_nodes
        new_nodes = list(new_node.iter(normal.upper))
        # If we want to insert a column (i.e. vertical) at the beginning/end,
        # we need a row (i.e. horizontal) to get the first/last column.
        if rel_node is None:
            rel_node = self.get_end_node(normal.lower)
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
        from pdf2gtfs.datastructures.table.fields import EmptyField

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
        node = self.get_end_node(d.opposite, node=node)
        while node:
            yield node
            node = node.get_neighbor(d)
