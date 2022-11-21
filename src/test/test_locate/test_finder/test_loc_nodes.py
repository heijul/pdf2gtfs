from config import Config
from locate import Location
from locate.finder import Stop
from locate.finder.cost import StartCost
from locate.finder.loc_nodes import Node, Nodes
from locate.finder.types import StopPosition
from test_locate.test_finder import (
    get_stops_and_dummy_df, get_stops_from_stops_list)
from test import P2GTestCase


class TestNode(P2GTestCase):
    @classmethod
    def setUpClass(cls: P2GTestCase, **kwargs) -> None:
        super().setUpClass(False, True)

    def setUp(self) -> None:
        Config.average_speed = 10
        stops_list, self.df = get_stops_and_dummy_df(5)
        self.stops = get_stops_from_stops_list(stops_list)
        self.nodes = Nodes(self.df, self.stops)

    def get_stop_positions(self) -> dict[Stop: list[StopPosition]]:
        stop_positions = {}
        idx = 0
        for stop_num, stop in enumerate(self.stops.stops):
            stop_positions[stop] = []
            name = stop.name
            lat = 47.8 + stop_num / 1000
            lon = 7.9 + stop_num / 1000

            for i in range(3):
                lat += i / 10000
                lon += i / 10000
                stop_positions[stop].append(
                    StopPosition(idx, name, name, lat, lon, i * 2, i * 2))
                idx += 1
        return stop_positions

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
        positions = self.get_stop_positions()
        stop = list(positions.keys())[0]
        p_node = self.nodes.get_or_create(stop, positions[stop][0])
        p_node.cost = StartCost.from_cost(p_node.cost)
        stop = stop.next
        node = self.nodes.get_or_create(stop, positions[stop][1])
        self.assertFalse(node.has_parent)
        node.update_parent_if_better(p_node)
        self.assertTrue(node.has_parent)

    def test_set_parent(self) -> None:
        positions = self.get_stop_positions()
        stop = list(positions.keys())[0]
        parent1 = self.nodes.get_or_create(stop, positions[stop][0])
        parent1.cost = StartCost.from_cost(parent1.cost)
        parent2 = self.nodes.get_or_create(stop, positions[stop][1])
        stop = stop.next
        child = self.nodes.get_or_create(stop, positions[stop][1])
        self.assertFalse(child.has_parent)
        child.set_parent(parent2)
        self.assertFalse(child.has_parent)
        child.set_parent(parent1)
        self.assertTrue(child.has_parent)
        parent2.cost = StartCost.from_cost(parent2.cost)
        child.set_parent(parent2)
        # Costs are not compared..
        self.assertTrue(child.has_parent)
        self.assertEqual(parent2, child.parent)

    def test_update_parent_if_better(self) -> None:
        positions = self.get_stop_positions()
        stop = list(positions.keys())[0]
        parent0 = self.nodes.get_or_create(stop, positions[stop][0])
        parent0.cost = StartCost.from_cost(parent0.cost)
        parent1 = self.nodes.get_or_create(stop, positions[stop][1])
        parent1.cost = StartCost.from_cost(parent1.cost)
        parent2 = self.nodes.get_or_create(stop, positions[stop][2])
        parent2.cost = StartCost.from_cost(parent2.cost)
        stop = stop.next
        child = self.nodes.get_or_create(stop, positions[stop][1])
        self.assertFalse(child.has_parent)
        child.update_parent_if_better(parent2)
        self.assertTrue(child.has_parent)
        self.assertEqual(parent2, child.parent)
        child.update_parent_if_better(parent1)
        self.assertEqual(parent1, child.parent)
        child.update_parent_if_better(parent0)
        self.assertEqual(parent0, child.parent)

    def test__select_better_parent(self) -> None:
        positions = self.get_stop_positions()
        stop = list(positions.keys())[0]
        parent0 = self.nodes.get_or_create(stop, positions[stop][0])
        parent0.cost = StartCost.from_cost(parent0.cost)
        parent1 = self.nodes.get_or_create(stop, positions[stop][1])
        parent1.cost = StartCost.from_cost(parent1.cost)
        loc = positions[stop][2][3:5]
        parent2 = self.nodes._create_existing_node(stop, Location(*loc))
        parent2.cost = StartCost.from_cost(parent2.cost)
        stop = stop.next
        child = self.nodes.get_or_create(stop, positions[stop][1])
        self.assertEqual(
            parent0, child._select_better_parent(parent0, parent1))
        self.assertEqual(
            parent2, child._select_better_parent(parent0, parent2))
        self.assertEqual(
            parent2, child._select_better_parent(parent1, parent2))

    def test_close_nodes(self) -> None:
        stop_positions = self.get_stop_positions()
        stop_nodes = {}
        for stop, positions in stop_positions.items():
            stop_nodes[stop] = []
            for position in positions:
                stop_nodes[stop].append(
                    self.nodes.get_or_create(stop, position))
        for i, (stop, nodes) in enumerate(list(stop_nodes.items())[:-1]):
            with self.subTest(i=i):
                for node in nodes:
                    for other_node in stop_nodes[stop.next]:
                        self.assertTrue(node.close_nodes(other_node))
                        self.assertFalse(node.close_nodes(other_node, 1))

    def test_compare_node_type(self) -> None:
        positions = self.get_stop_positions()
        stop = list(positions.keys())[0]
        node = self.nodes.get_or_create(stop, positions[stop][0])
        node.cost = StartCost.from_cost(node.cost)
        m_node = self.nodes.get_or_create_missing(stop, positions[stop][1])
        m_node.cost = StartCost.from_cost(m_node.cost)
        loc = positions[stop][2][3:5]
        e_node = self.nodes._create_existing_node(stop, Location(*loc))
        e_node.cost = StartCost.from_cost(e_node.cost)
        self.assertEqual(e_node, Node.compare_node_type(e_node, node))
        self.assertEqual(e_node, Node.compare_node_type(e_node, m_node))
        self.assertEqual(node, Node.compare_node_type(node, m_node))

    def test_update_neighbors(self) -> None:
        stop_positions = self.get_stop_positions()
        stop_nodes = {}
        for i, (stop, positions) in enumerate(stop_positions.items()):
            stop_nodes[stop] = []
            for position in positions:
                node = self.nodes.get_or_create(stop, position)
                stop_nodes[stop].append(node)
                if i == 0:
                    node.cost = StartCost.from_cost(node.cost)
        for stop, nodes in list(stop_nodes.items())[:-1]:
            for node in nodes:
                node.update_neighbors()
        # Last nodes do not have neighbors.
        for j, nodes in enumerate(list(stop_nodes.values())[1:]):
            with self.subTest(j=j):
                for k, node in enumerate(nodes):
                    with self.subTest(k=k):
                        self.assertTrue(node.visited or node.stop.is_last)
                        if j >= 1:
                            self.assertTrue(node.has_parent)


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
