""" Contains the DoublyLinkedList and its LLNode. """

from __future__ import annotations

from typing import Generic, Iterator, Type, TypeVar


# The node type. In general, this should be a TypeVar bound to
# the class that is subclassing LLNode.
NT = TypeVar("NT", bound="LLNode")
NT2 = TypeVar("NT2", bound="LLNode")
DLL = TypeVar("DLL", bound="DoublyLinkedList")


class LLNode(Generic[NT]):
    """ A single node of a linked list. """
    def __init__(self, *args, **kwargs) -> None:
        self._prev: NT | None = None
        self._next: NT | None = None
        self._list: DoublyLinkedList[NT] | None = None
        super().__init__(*args, **kwargs)

    def _set_neighbor(self, which_attr: str, ref_attr: str,
                      neighbor: NT | None) -> None:
        """ Ensure the neighbor is symmetric. """
        assert self != neighbor
        assert which_attr in ["_prev", "_next"]
        assert ref_attr in ["prev", "next"]
        old_neighbor = getattr(self, which_attr)
        setattr(self, which_attr, neighbor)
        # Prevent dangling references.
        if old_neighbor:
            setattr(old_neighbor, ref_attr, None)
        if neighbor is None or getattr(neighbor, ref_attr) == self:
            return
        setattr(neighbor, ref_attr, self)

    @property
    def list(self) -> DoublyLinkedList[NT] | None:
        """ Reference to the parent object.

        :return: The doubly linked list, this node belongs to or None, if it
         does not belong to any list yet.
        """
        return self._list

    @list.setter
    def list(self, value: DoublyLinkedList[NT] | None) -> None:
        self._list = value

    @property
    def prev(self) -> NT | None:
        """ The previous node or None, if this is the first node. """
        return self._prev

    @prev.setter
    def prev(self, value: NT | None) -> None:
        self._set_neighbor("_prev", "next", value)

    @property
    def next(self) -> NT | None:
        """ The next node or None, if this is the last node. """
        return self._next

    @next.setter
    def next(self, value: NT | None) -> None:
        self._set_neighbor("_next", "prev", value)


class DoublyLinkedList(Generic[NT]):
    """ A simple doubly linked list. """
    def __init__(self, first: NT | None = None, last: NT | None = None,
                 *args, **kwargs) -> None:
        self._first: NT = first
        self._last: NT = last if last is None else first
        super().__init__(*args, **kwargs)

    @classmethod
    def from_objects(cls: Type[DLL], objects: list[NT]) -> DLL:
        """ Create a new DLList, using the provided objects. """
        first = objects[0]
        current = first
        for next_ in objects[1:]:
            current.next = next_
            current = next_
        return cls(first, current)

    @property
    def first(self) -> NT:
        """ The first item in the list.

        If a new item was prepended to the list, first will automatically
        be updated, the next time it was queried.
        """
        # A new node was prepended to the list.
        if self._first and self._first.prev:
            while self._first.prev:
                self._first = self._first.prev
        return self._first

    @first.setter
    def first(self, node: NT) -> None:
        """ Set the first node, which must not have a prev neighbor.

        This will also set `last`; either to node, if it has no next neighbor,
        or the furthest next neighbor of node.

        :param node: The node that will be the first node.
        """
        assert node.prev is None
        self._first = node
        while node.next:
            node = node.next
        self._last = node

    @property
    def last(self) -> NT:
        """ The last item in the list. This may be equal to the first item.

        If a new item was appended to the list, last will automatically
        be updated, the next time it was queried.
        """
        # A new node was appended to the list.
        if self._last and self._last.next:
            while self._last.next:
                self._last = self._last.next
        return self._last

    @last.setter
    def last(self, node: NT) -> None:
        assert node.next is None
        self._last = node
        while node.prev:
            node = node.prev
        self._first = node

    def insert(self, where: str, rel_node: NT | None, node: NT) -> None:
        """ Insert the node relative to rel_node, based on where.

        :param where: One of "prev" and "next". Roughly, if where is set to
         "next", rel_node.next == node. Analogous for "prev".
        :param rel_node: An existing node in this list, that is used to
        insert the new node.
        :param node: The node that should be inserted.
        """
        assert where in ("prev", "next")
        assert self.first is None or rel_node is not None
        if rel_node is None:
            setattr(self, "first" if where == "prev" else "last", node)
            return
        previous_neighbor = getattr(rel_node, where)
        # Need to set previous_neighbor first, because we use
        # prev/next to update last/first.
        if previous_neighbor:
            setattr(node, where, previous_neighbor)
        setattr(rel_node, where, node)

    def prepend(self, anchor: NT, *,
                node: NT = None,
                fields: list[NT2] = None) -> None:
        """ Inserts a new node before rel_node.

        Either node xor fields should be given. If fields is given, a
        new node will be constructed using the fields, otherwise node will
        be prepended.

        :param anchor: The node, the new node will be prepended relative to.
        :param node: The node that will be prepended.
        :param fields: The fields a new node will be constructed from,
            which will be prepended.
        """
        # Only allow a single argument of the two.
        assert node and fields is None or node is None and fields
        if fields:
            node = anchor.construct_from_fields(fields, add_empty=True)
        self.insert("prev", anchor, node)

    def append(self, node: NT) -> None:
        """ Adds the node to the end of the table.

        :param node: A single node.
        """
        self.insert("next", self.last, node)

    def __iter__(self) -> Iterator[NT]:
        return self.__next__()

    def __next__(self) -> NT:
        field = self.first
        while field:
            yield field
            field = field.next

    def __getitem__(self, key: slice | int) -> NT | list[NT]:
        if isinstance(key, int):
            if key < 0:
                node = self.last
                i = -1
                while node:
                    if i == key:
                        return node
                    node = node.prev
                    i -= 1
            else:
                for i, field in enumerate(self):
                    if i != key:
                        continue
                    return field
            raise IndexError("linked list index out of range")
        if isinstance(key, slice):
            # TODO: performance/space
            return list(self)[key]
        raise TypeError(
            "linked list indices must be integers or slices, not {type(key)}")

    def __len__(self) -> int:
        return sum([1 for _ in self])
