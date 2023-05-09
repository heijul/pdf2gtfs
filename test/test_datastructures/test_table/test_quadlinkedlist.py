from unittest import TestCase

from pdf2gtfs.datastructures.table.nodes import QuadNode
from pdf2gtfs.datastructures.table.quadlinkedlist import QuadLinkedList


class TestQuadLinkedList(TestCase):
    def setUp(self) -> None:
        self.node1 = QuadNode()
        self.node2 = QuadNode()
        self.qll = QuadLinkedList(self.node1, self.node2)

    def test_properties(self) -> None:
        self.skipTest("Not implemented yet!")

    def test_get_end_node(self) -> None:
        self.skipTest("Not implemented yet!")

    def test_set_end_node(self) -> None:
        self.skipTest("Not implemented yet!")

    def test_update_end_node(self) -> None:
        self.skipTest("Not implemented yet!")

    def test_get_first(self) -> None:
        self.skipTest("Not implemented yet!")

    def test_get_list(self) -> None:
        self.skipTest("Not implemented yet!")

    def test_from_objects(self) -> None:
        self.skipTest("Check if used.")

    def test_insert(self) -> None:
        self.skipTest("Not implemented yet!")

    def test_get_series(self) -> None:
        self.skipTest("Not implemented yet!")

    def test_get_bbox_of(self) -> None:
        self.skipTest("Not implemented yet!")

    def test_iter(self) -> None:
        self.skipTest("Not implemented yet!")
