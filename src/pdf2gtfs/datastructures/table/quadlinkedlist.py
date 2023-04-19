""" The LinkedLists used as base classes for Table, Field, Row and Col. """

from __future__ import annotations

from typing import (
    Generator, Generic, Iterator, Optional, Type, TypeAlias, TypeVar,
    )

from pdf2gtfs.datastructures.pdftable.bbox import BBox
from pdf2gtfs.datastructures.table.direction import (
    Direction, E, H, N, Orientation, S, V, W,
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
        for row_field in self.get_series(H, self.top):
            for col_field in self.get_series(V, row_field):
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

    def get_end_node(self, d: Direction) -> OQN:
        """ Return one of the end nodes in the given direction.

        :param d: The direction to look for the end node in.
        """
        node: OQN = self._get_saved_node(d.p_end)
        o = d.default_orientation
        d2 = o.normal.lower if d == o.lower else o.normal.upper
        if not node.has_neighbors(d=d) and not node.has_neighbors(d=d2):
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

    def _update_end_node(self, d: Direction, start: QN) -> None:
        """ Update the end node in the given direction to the farthest/last
        node in that direction.

        Always ensures that the end node in the lower direction of an
        orientation is also the end node in the lower direction of the
        orientation's normal orientation. That is, if d is N (i.e. V.lower)
        the end node the same as when d is W (i.e. H.lower). Analogous for S/E.

        :param d: The direction to look for the last node.
        :param start: The node to use to look for the end node in d.
        """
        o = d.default_orientation
        node = self.get_first(d, start)
        d2 = o.normal.lower if d == o.lower else o.normal.upper
        node = self.get_first(d2, node)
        self._set_end_node(d, node)

    def get_first(self, d: Direction, node: QN) -> QN:
        """ Return the final node in the given direction, starting at node.

        :param d: The direction to get the final node in.
        :param node: The node to start the search at.
        :return: Either node, if it is the last node or a node that is an
            extended neighbor (i.e. neighbor/neighbors neighbor/...).
        """
        while node.has_neighbors(d=d):
            node = node.get_neighbor(d)
        return node

    def get_list(self, o: Orientation, node: OQN = None) -> list[QN]:
        """ Return the full list of nodes in the given orientation.

        :param o: The orientation the nodes will be in.
        :param node: The node used to get a specific row/column. If set to
         None, the first/top node will be used instead.
        """
        if not node:
            node = self.get_end_node(o.lower)
        return list(self.iter(o.upper, node))

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

    def get_series(self, o: Orientation, node: QN) -> Generator[QN]:
        """ The row or column the node resides in.

        :param o: The orientation of the series, i.e. whether to return
            row (H) or column (V).
        :param node: The node in question.
        :return: A generator that yields all objects in the series.
        """
        return self.iter(o.upper, node)

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
        node = self.get_first(d.opposite, node)
        while node:
            yield node
            node = node.get_neighbor(d)
