from config import Config
from locate.finder import Nodes
from test_locate.test_finder import (
    get_stops_and_dummy_df, get_stops_from_stops_list)
from test import P2GTestCase


class TestNode(P2GTestCase):
    def setUp(self) -> None:
        Config.average_speed = 10
        stops_list, self.df = get_stops_and_dummy_df()
        self.stops = get_stops_from_stops_list(stops_list)
        self.nodes = Nodes(self.df, self.stops)

    def test_get_neighbors(self) -> None:
        node_heap = self.nodes._node_heap

        i = 0
        while node_heap.first:
            with self.subTest(i=i):
                node = node_heap.pop()
                if node.stop == self.stops.last:
                    continue
                neighbors = node.get_close_neighbors()
                # Check that the neighbors are close
                for neigbor in neighbors:
                    self.assertTrue(node.close_nodes(neigbor))
                # Check that neighbors all have the correct stop.
                for neighbor in neighbors:
                    self.assertEqual(node.stop.next, neighbor.stop)
                i += 1

    def test_update_parent_if_lower_cost(self) -> None:
        # TODO:
        pass
