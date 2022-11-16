from config import Config
from locate.finder.loc_nodes import Nodes
from test_locate.test_finder import (
    get_stops_and_dummy_df, get_stops_from_stops_list)
from test import P2GTestCase


class TestNode(P2GTestCase):
    def setUp(self) -> None:
        Config.average_speed = 10
        stops_list, self.df = get_stops_and_dummy_df()
        self.stops = get_stops_from_stops_list(stops_list)
        self.nodes = Nodes(self.df, self.stops)

    def test___comparisons(self) -> None:
        ...

    def test_get_close_neighbors(self) -> None:
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

    def test_dist_exact(self) -> None:
        ...

    def test_cost_with_parent(self) -> None:
        ...

    def test_construct_route(self) -> None:
        ...

    def test_has_parent(self) -> None:
        ...

    def test_set_parent(self) -> None:
        ...

    def test_update_parent_if_better(self) -> None:
        ...

    def test__select_better_parent(self) -> None:
        ...

    def test_get_max_dist(self) -> None:
        ...

    def test_close_nodes(self) -> None:
        ...

    def test_compare_node_type(self) -> None:
        ...

    def test_update_neighbors(self) -> None:
        ...


class TestMNode(P2GTestCase):
    def test_dist_exact(self) -> None:
        ...

    def test_get_max_dist(self) -> None:
        ...

    def test_cost_with_parent(self) -> None:
        ...

    def test_close_nodes(self) -> None:
        ...


class TestNodes(P2GTestCase):
    def test__initialize_dfs(self) -> None:
        ...

    def test_add(self) -> None:
        ...

    def test_create_nodes_for_stop(self) -> None:
        ...

    def test__create_node(self) -> None:
        ...

    def test__create_missing_node(self) -> None:
        ...

    def test__create_existing_node(self) -> None:
        ...

    def test_get_or_create(self) -> None:
        ...

    def test_create_missing_neighbor_for_node(self) -> None:
        ...

    def test_get_or_create_missing(self) -> None:
        ...

    def test_filter_df_by_stop(self) -> None:
        ...

    def test_get_min_node(self) -> None:
        ...

    def test_update_parent(self) -> None:
        ...

    def test_display_all_nodes(self) -> None:
        ...


class TestNodeHeap(P2GTestCase):
    def test_count(self) -> None:
        ...

    def test_add_node(self) -> None:
        ...

    def test__find_previous(self) -> None:
        ...

    def test_insert_after(self) -> None:
        ...

    def test_pop(self) -> None:
        ...

    def test_update(self) -> None:
        ...

    def test_remove(self) -> None:
        ...


class TestHeapNode(P2GTestCase):
    def test_node_cost(self) -> None:
        ...

    def test_valid_position(self) -> None:
        ...


def test_calculate_travel_cost_between() -> None:
    ...
