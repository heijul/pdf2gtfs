from unittest import TestCase

from pdf2gtfs.datastructures.table.linked_list import DoublyLinkedList, LLNode


class TestLLNode(TestCase):
    def setUp(self) -> None:
        self.node1 = LLNode("node1")
        self.node2 = LLNode("node2")
        self.node3 = LLNode("node3")

    def test_set_neighbor(self) -> None:
        ...

    def test_getattr(self) -> None:
        ...

    def test_prev_setter(self) -> None:
        self.node2.prev = self.node1
        self.assertEqual(self.node2.prev, self.node1)
        self.assertEqual(self.node1.next, self.node2)
        self.node2.prev = self.node3
        self.assertEqual(self.node2.prev, self.node3)
        self.assertEqual(self.node3.next, self.node2)
        self.assertIsNone(self.node1.prev)
        self.assertIsNone(self.node1.next)

    def test_next_setter(self) -> None:
        self.node1.next = self.node2
        self.assertEqual(self.node2.prev, self.node1)
        self.assertEqual(self.node1.next, self.node2)
        self.node3.next = self.node2
        self.assertEqual(self.node2.prev, self.node3)
        self.assertEqual(self.node3.next, self.node2)
        self.assertIsNone(self.node1.prev)
        self.assertIsNone(self.node1.next)


class TestDLList(TestCase):
    def test_from_objects(self) -> None:
        objects: list[LLNode[int]] = [LLNode(i) for i in range(3)]
        linked_list = DoublyLinkedList.from_objects(objects)
        # Ensure order.
        for a, b in zip(objects, linked_list):
            self.assertEqual(a.value, b.value)
        # Ensure nodes are linked.
        current = linked_list[0]
        for node in linked_list[1:]:
            self.assertEqual(current.next, node)
            self.assertEqual(node.prev, current)
            current = node
