from math import inf

from config import Config
from locate import Location
from locate.finder import Stop, Stops
from locate.finder.cost import StartCost
from locate.finder.loc_nodes import HeapNode, Node, NodeHeap, Nodes
from locate.finder.types import StopPosition
from test_locate.test_finder import (
    get_stops_and_dummy_df, get_stops_from_stops_list)
from test import P2GTestCase


def get_stop_positions(stops: Stops) -> dict[Stop: list[StopPosition]]:
    stop_positions = {}
    idx = 0
    for stop_num, stop in enumerate(stops.stops):
        stop_positions[stop] = []
        name = stop.name
        lat = 47.8 + stop_num / 1000
        lon = 7.9 + stop_num / 1000

        for i in range(1, 4):
            lat += i / 10000
            lon += i / 10000
            stop_positions[stop].append(
                StopPosition(idx, name, name, lat, lon, i * 2, i * 2))
            idx += 1
    return stop_positions


def node_heap_nodes(heap: NodeHeap) -> list[HeapNode]:
    node = heap.first
    nodes = []
    while node:
        nodes.append(node)
        node = node.next
    return nodes


class TestNode(P2GTestCase):
    @classmethod
    def setUpClass(cls: P2GTestCase, **kwargs) -> None:
        super().setUpClass(False, True)

    def setUp(self) -> None:
        Config.average_speed = 10
        stops_list, self.df = get_stops_and_dummy_df(5)
        self.stops = get_stops_from_stops_list(stops_list)
        self.nodes = Nodes(self.df, self.stops)

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
        positions = get_stop_positions(self.stops)
        stop = list(positions.keys())[0]
        p_node = self.nodes.get_or_create(stop, positions[stop][0])
        p_node.cost = StartCost.from_cost(p_node.cost)
        stop = stop.next
        node = self.nodes.get_or_create(stop, positions[stop][1])
        self.assertFalse(node.has_parent)
        node.update_parent_if_better(p_node)
        self.assertTrue(node.has_parent)

    def test_set_parent(self) -> None:
        positions = get_stop_positions(self.stops)
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
        positions = get_stop_positions(self.stops)
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
        positions = get_stop_positions(self.stops)
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
        stop_positions = get_stop_positions(self.stops)
        stop_nodes = {}
        for stop, positions in stop_positions.items():
            stop_nodes[stop] = []
            for position in positions:
                stop_nodes[stop].append(
                    self.nodes.get_or_create(stop, position))
        Config.disable_close_node_check = False
        for i, (stop, nodes) in enumerate(list(stop_nodes.items())[:-1]):
            with self.subTest(i=i):
                for node in nodes:
                    for other_node in stop_nodes[stop.next]:
                        self.assertTrue(node.close_nodes(other_node))
                        self.assertFalse(node.close_nodes(other_node, 1))

    def test_compare_node_type(self) -> None:
        positions = get_stop_positions(self.stops)
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
        stop_positions = get_stop_positions(self.stops)
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
    @classmethod
    def setUpClass(cls: P2GTestCase, **kwargs) -> None:
        super().setUpClass(False, True)

    def setUp(self) -> None:
        Config.average_speed = 10
        stops_list, self.df = get_stops_and_dummy_df(5)
        self.stops = get_stops_from_stops_list(stops_list)
        self.nodes = Nodes(self.df, self.stops)

    def test_dist_exact(self) -> None:
        positions = get_stop_positions(self.stops)
        stop = list(positions.keys())[0]
        parent = self.nodes.get_or_create(stop, positions[stop][0])
        parent.cost = StartCost.from_cost(parent.cost)
        node = self.nodes.get_or_create(stop, positions[stop][1])
        node.cost = StartCost.from_cost(node.cost)
        stop = stop.next
        m_node = self.nodes.get_or_create_missing(stop, positions[stop][1])
        self.assertFalse(m_node.has_parent)
        with self.assertRaises(NotImplementedError):
            m_node.dist_exact(node)
        m_node.set_parent(parent)
        self.assertEqual(parent.dist_exact(node), m_node.dist_exact(node))

    def test_get_max_dist(self) -> None:
        positions = get_stop_positions(self.stops)
        stop = list(positions.keys())[0]
        parent = self.nodes.get_or_create(stop, positions[stop][0])
        parent.cost = StartCost.from_cost(parent.cost)
        stop = stop.next
        m_node = self.nodes.get_or_create_missing(stop, positions[stop][1])
        self.assertFalse(m_node.has_parent)
        self.assertEqual(inf, m_node.get_max_dist())
        m_node.set_parent(parent)
        self.assertAlmostEqual(666.666, m_node.get_max_dist(), 2)

    def test_cost_with_parent(self) -> None:
        Config.missing_node_cost = 200
        positions = get_stop_positions(self.stops)
        stop = list(positions.keys())[0]
        parent = self.nodes.get_or_create(stop, positions[stop][0])
        parent.cost = StartCost.from_cost(parent.cost)
        parent2 = self.nodes.get_or_create(stop, positions[stop][1])
        parent2.cost = StartCost.from_cost(parent2.cost)
        stop = stop.next
        m_node = self.nodes.get_or_create_missing(stop, positions[stop][1])
        cost_with_parent = m_node.cost_with_parent(parent)
        cost_with_parent2 = m_node.cost_with_parent(parent2)
        self.assertEqual(204, cost_with_parent.as_float)
        self.assertEqual(208, cost_with_parent2.as_float)
        m_node.set_parent(parent)
        self.assertEqual(cost_with_parent, m_node.cost)
        m_node.set_parent(parent2)
        self.assertEqual(cost_with_parent2, m_node.cost)

    def test_close_nodes(self) -> None:
        positions = get_stop_positions(self.stops)
        stop = list(positions.keys())[0]
        parent = self.nodes.get_or_create(stop, positions[stop][0])
        parent.cost = StartCost.from_cost(parent.cost)
        stop = stop.next
        m_node = self.nodes.get_or_create_missing(stop, positions[stop][1])
        stop = stop.next
        child1 = self.nodes.get_or_create(stop, positions[stop][0])
        child2 = self.nodes.get_or_create(stop, positions[stop][1])
        # Far away stop.
        loc = m_node.loc + Location(1, 1)
        child3 = self.nodes._create_existing_node(stop, loc)
        self.assertFalse(m_node.parent)
        self.assertTrue(m_node.close_nodes(child1))
        self.assertTrue(m_node.close_nodes(child2))
        self.assertTrue(m_node.close_nodes(child3))
        m_node.set_parent(parent)
        self.assertTrue(m_node.close_nodes(child1))
        self.assertTrue(m_node.close_nodes(child2))
        self.assertFalse(m_node.close_nodes(child3))
        Config.disable_close_node_check = True
        self.assertTrue(m_node.close_nodes(child1))
        self.assertTrue(m_node.close_nodes(child2))
        self.assertTrue(m_node.close_nodes(child3))


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
    @classmethod
    def setUpClass(cls: P2GTestCase, **kwargs) -> None:
        super().setUpClass(False, True)

    def setUp(self) -> None:
        Config.average_speed = 10
        stops_list, self.df = get_stops_and_dummy_df(5)
        self.stops = get_stops_from_stops_list(stops_list)
        self.nodes = Nodes(self.df, self.stops)
        self.heap = NodeHeap()
        positions = get_stop_positions(self.stops)
        stop = list(positions.keys())[0]
        self.node0 = self.nodes.get_or_create(stop, positions[stop][0])
        self.node0.cost = StartCost.from_cost(self.node0.cost)
        self.node1 = self.nodes.get_or_create(stop, positions[stop][1])
        self.node1.cost = StartCost.from_cost(self.node1.cost)
        stop = stop.next
        self.node2 = self.nodes.get_or_create(stop, positions[stop][1])
        self.node3 = self.nodes.get_or_create(stop, positions[stop][0])
        self.node2.set_parent(self.node0)
        self.node3.set_parent(self.node1)

    def test_count(self) -> None:
        positions = get_stop_positions(self.stops)
        stop = list(positions.keys())[0]
        parent = self.nodes.get_or_create(stop, positions[stop][0])
        parent.cost = StartCost.from_cost(parent.cost)
        node0 = self.nodes.get_or_create(stop, positions[stop][1])
        node0.cost = StartCost.from_cost(node0.cost)
        stop = stop.next
        node1 = self.nodes.get_or_create(stop, positions[stop][0])
        node2 = self.nodes.get_or_create(stop, positions[stop][2])
        node1.set_parent(parent)
        node2.set_parent(parent)
        self.assertEqual(0, self.heap.count)
        self.heap.add_node(node0)
        self.assertEqual(1, self.heap.count)
        self.heap.add_node(node1)
        self.assertEqual(2, self.heap.count)
        self.heap.add_node(node2)
        self.assertEqual(3, self.heap.count)
        self.heap.pop()
        self.assertEqual(2, self.heap.count)
        self.heap.pop()
        self.assertEqual(1, self.heap.count)
        self.heap.pop()
        self.assertEqual(0, self.heap.count)

    def test_add_node(self) -> None:
        positions = get_stop_positions(self.stops)
        stop = list(positions.keys())[0]
        parent = self.nodes.get_or_create(stop, positions[stop][0])
        parent.cost = StartCost.from_cost(parent.cost)
        node0 = self.nodes.get_or_create(stop, positions[stop][1])
        node0.cost = StartCost.from_cost(node0.cost)
        stop = stop.next
        node1 = self.nodes.get_or_create(stop, positions[stop][0])
        node2 = self.nodes.get_or_create(stop, positions[stop][2])
        node1.set_parent(parent)
        node2.set_parent(parent)
        self.assertIsNone(self.heap.first)
        self.heap.add_node(node1)
        self.assertEqual(node1, self.heap.first.node)
        self.heap.add_node(node0)
        self.assertEqual(node0, self.heap.first.node)
        self.heap.add_node(node2)
        hnode = self.heap.first
        self.assertEqual(node0, hnode.node)
        self.assertEqual(node1, hnode.next.node)
        self.assertEqual(node2, hnode.next.next.node)

    def test__find_previous(self) -> None:
        nodes = [self.node1, self.node2, self.node0, self.node3]

        node = nodes[0]
        self.heap.add_node(node)
        prev_heap_node = self.heap.first

        node = nodes[1]
        heap_node = HeapNode(node)
        self.assertEqual(prev_heap_node, self.heap._find_previous(heap_node))
        self.heap.add_node(node)
        prev_heap_node = self.heap.node_map[node]

        node = nodes[2]
        heap_node = HeapNode(node)
        self.assertEqual(None, self.heap._find_previous(heap_node))
        self.heap.node_map[node] = heap_node

        node = nodes[3]
        heap_node = HeapNode(node)
        self.assertEqual(prev_heap_node, self.heap._find_previous(heap_node))
        self.heap.node_map[node] = heap_node

    def test_insert_after(self) -> None:
        self.heap.add_node(self.node0)
        heap_node0 = self.heap.node_map[self.node0]
        heap_node1 = HeapNode(self.node1)
        self.heap.node_map[self.node1] = heap_node1
        heap_node2 = HeapNode(self.node2)
        self.heap.node_map[self.node2] = heap_node2

        self.heap.insert_after(None, heap_node1)
        self.assertEqual(heap_node1, self.heap.first)
        self.assertEqual(heap_node1.next, heap_node0)
        self.assertEqual(heap_node0.prev, heap_node1)

        self.heap.insert_after(heap_node1, heap_node2)
        self.assertEqual(heap_node1.next, heap_node2)
        self.assertEqual(heap_node0.prev, heap_node2)
        self.assertEqual(heap_node2.next, heap_node0)
        self.assertEqual(heap_node2.prev, heap_node1)

    def test_pop(self) -> None:
        self.heap.add_node(self.node0)
        self.heap.add_node(self.node2)
        self.heap.add_node(self.node3)
        heap_pop_order = (self.node0, self.node2, self.node1, self.node3)
        self.assertEqual(3, self.heap.count)
        self.assertEqual(heap_pop_order[0], self.heap.pop())
        self.assertEqual(2, self.heap.count)
        self.assertEqual(heap_pop_order[1], self.heap.pop())
        self.assertEqual(1, self.heap.count)
        self.heap.add_node(self.node1)
        self.assertEqual(2, self.heap.count)
        self.assertEqual(heap_pop_order[2], self.heap.pop())
        self.assertEqual(1, self.heap.count)
        self.assertEqual(heap_pop_order[3], self.heap.pop())
        self.assertEqual(0, self.heap.count)

    def test_update(self) -> None:
        self.heap.add_node(self.node0)
        self.heap.add_node(self.node1)
        self.node2.cost.node_cost = 0
        self.heap.add_node(self.node2)
        self.heap.add_node(self.node3)
        nodes1 = node_heap_nodes(self.heap)
        nodes = [self.node0, self.node1, self.node2, self.node3]
        self.assertListEqual(nodes, [n.node for n in nodes1])
        # This will reduce the cost of node3
        self.node3.set_parent(self.node0)
        self.heap.update(self.node3)
        self.assertListEqual(nodes, [n.node for n in nodes1])
        self.node3.cost.node_cost -= 1
        self.heap.update(self.node3)
        nodes2 = node_heap_nodes(self.heap)
        nodes = [self.node0, self.node1, self.node3, self.node2]
        self.assertListEqual(nodes, [n.node for n in nodes2])

    def test_remove(self) -> None:
        self.heap.add_node(self.node0)
        self.heap.add_node(self.node1)
        self.heap.add_node(self.node2)
        self.heap.add_node(self.node3)
        heap_nodes = node_heap_nodes(self.heap)
        count = 4

        while heap_nodes:
            node = heap_nodes.pop(0)
            self.heap.remove(node)
            count -= 1
            self.assertEqual(count, self.heap.count)


class TestHeapNode(P2GTestCase):
    @classmethod
    def setUpClass(cls: P2GTestCase, **kwargs) -> None:
        super().setUpClass(False, True)

    def setUp(self) -> None:
        Config.average_speed = 10
        stops_list, self.df = get_stops_and_dummy_df(5)
        self.stops = get_stops_from_stops_list(stops_list)
        self.nodes = Nodes(self.df, self.stops)

    def test_valid_position(self) -> None:
        positions = get_stop_positions(self.stops)
        stop = list(positions.keys())[0]
        parent = self.nodes.get_or_create(stop, positions[stop][0])
        parent.cost = StartCost.from_cost(parent.cost)
        node = self.nodes.get_or_create(stop, positions[stop][1])
        node.cost = StartCost.from_cost(node.cost)
        stop = stop.next
        node1 = self.nodes.get_or_create(stop, positions[stop][0])
        node2 = self.nodes.get_or_create(stop, positions[stop][2])
        node1.set_parent(parent)
        node2.set_parent(parent)
        node_heap = NodeHeap()
        node_heap.add_node(parent)
        node_heap.add_node(node1)
        node_heap.add_node(node2)
        heap_nodes = []
        node = node_heap.first
        while True:
            heap_nodes.append(node)
            node = node.next
            if not node:
                break
        self.assertTrue(all([node.valid_position for node in heap_nodes]))
        # Switch 1 and 2.
        heap_nodes[1].next = None
        heap_nodes[1].prev = heap_nodes[2]
        heap_nodes[0].next = heap_nodes[2]
        heap_nodes[2].prev = heap_nodes[0]
        heap_nodes[2].next = heap_nodes[1]
        self.assertTrue(heap_nodes[0].valid_position)
        self.assertFalse(heap_nodes[1].valid_position)
        self.assertFalse(heap_nodes[2].valid_position)


def test_calculate_travel_cost_between() -> None:
    ...
