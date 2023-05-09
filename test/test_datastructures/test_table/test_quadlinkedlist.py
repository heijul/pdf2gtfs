from unittest import TestCase

from pdf2gtfs.datastructures.table.nodes import QuadNode
from pdf2gtfs.datastructures.table.quadlinkedlist import QuadLinkedList


def create_rectangle_nodes(num_col: int = 4, num_row: int = 5
                           ) -> list[QuadNode]:
    nodes = [QuadNode() for _ in range(num_col * num_row)]
    for i in range(num_col * num_row):
        if i % num_col:
            nodes[i - 1].next = nodes[i]
        if i >= num_col:
            nodes[i - num_col].below = nodes[i]
    return nodes


class TestQuadLinkedList(TestCase):
    def setUp(self) -> None:
        self.nodes = create_rectangle_nodes()
        self.qll = QuadLinkedList(self.nodes[0], self.nodes[-1])

    def test_properties(self) -> None:
        self.nodes = create_rectangle_nodes()
        self.qll = QuadLinkedList(self.nodes[0], self.nodes[-1])
        self.assertEqual(self.nodes[0], self.qll.left)
        self.assertEqual(self.nodes[0], self.qll.top)
        self.assertEqual(self.nodes[-1], self.qll.right)
        self.assertEqual(self.nodes[-1], self.qll.bot)
        # TODO: Add setter tests.

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
