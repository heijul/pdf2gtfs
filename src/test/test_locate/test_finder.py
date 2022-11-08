from math import inf
from typing import TypeAlias
from unittest import mock, TestCase

import pandas as pd

from config import Config
from datastructures.gtfs_output.stop import GTFSStopEntry
from datastructures.gtfs_output.stop_times import Time
from locate.finder.cost import Cost
from locate.finder.loc_nodes import Nodes
from locate.finder.stops import Stops
from test_locate import create_handler


DF: TypeAlias = pd.DataFrame


class TestStop(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        Config.load_default_config()

    def setUp(self) -> None:
        stop_list = [("0", "stop_0"), ("1", "stop_1")]
        self.stops = get_stops_from_stops_list(stop_list)
        Config.average_speed = 15

    def test_exists(self) -> None:
        ...

    @mock.patch("locate.finder.stops.Stops.get_avg_time_between")
    def test_set_distance_bounds(self, get_avg_time_between) -> None:
        Config.average_speed = 15
        min_dist = Config.min_travel_distance
        Config.average_travel_distance_offset = 2
        get_avg_time_between.side_effect = [
            Time(minutes=minutes) for minutes in [1, 2, 12, 0]]
        expected_lower = [min_dist, min_dist, 2500, min_dist]
        expected_mid = [250, 500, 3000, 0]
        expected_upper = [750, 1000, 3500, 0]
        stop_1 = self.stops.first
        for i in range(3):
            with self.subTest(i=i):
                lower, mid, upper = stop_1._get_distance_bounds()
                self.assertEqual(expected_lower[i], lower)
                self.assertEqual(expected_mid[i], mid)
                self.assertEqual(expected_upper[i], upper)

    def test_before(self) -> None:
        stop_1 = self.stops.first
        stop_2 = stop_1.next
        stop_3 = stop_2.next
        self.assertTrue(stop_1.before(stop_2))
        self.assertFalse(stop_2.before(stop_1))
        self.assertTrue(stop_1.before(stop_3))
        self.assertFalse(stop_2.before(stop_2))

    def test_after(self) -> None:
        stop_1 = self.stops.first
        stop_2 = stop_1.next
        stop_3 = stop_2.next
        self.assertFalse(stop_1.after(stop_2))
        self.assertTrue(stop_2.after(stop_1))
        self.assertTrue(stop_3.after(stop_1))
        self.assertFalse(stop_2.after(stop_2))

    def test_avg_time_to_next(self) -> None:
        # TODO: Ignore for now cause we'd need a working handler + stop_times
        pass


class TestCost(TestCase):
    def setUp(self) -> None:
        self.cost_1 = Cost(1, 2, 3, 4)
        self.cost_2 = Cost(5, 4, 3, 2)
        self.cost_3 = Cost(1, 2, 3, 4)
        self.cost_4 = Cost(4, 4, 4, 4)
        self.cost_5 = Cost(4, 4, 3, 5)
        self.cost_inf = Cost(1, inf, 1, 1)

    def test_from_cost(self) -> None:
        self.assertNotEqual(id(self.cost_1), id(Cost.from_cost(self.cost_1)))
        self.assertEqual(self.cost_1, Cost.from_cost(self.cost_1))
        self.assertEqual(self.cost_2, Cost.from_cost(self.cost_2))
        self.assertEqual(self.cost_3, Cost.from_cost(self.cost_3))

        self.assertEqual(self.cost_3, Cost.from_cost(self.cost_1))

    def test_eq(self) -> None:
        self.assertEqual(self.cost_1, self.cost_1)
        self.assertEqual(self.cost_1, self.cost_3)
        self.assertEqual(self.cost_4, self.cost_5)
        self.assertEqual(self.cost_3, self.cost_1)

        self.assertNotEqual(self.cost_1, self.cost_4)

        self.assertEqual(self.cost_inf, self.cost_inf)
        self.assertNotEqual(self.cost_1, self.cost_inf)
        # Stop ordering matters.
        self.assertNotEqual(self.cost_3, self.cost_2)
        self.assertNotEqual(self.cost_3.costs, self.cost_2.costs)

    def test_lt(self) -> None:
        self.assertLess(self.cost_1, self.cost_4)
        self.assertLess(self.cost_2, self.cost_4)

    def test_le(self) -> None:
        self.assertLessEqual(self.cost_1, self.cost_2)
        self.assertGreater(self.cost_2, self.cost_1)
        self.assertGreater(self.cost_2, self.cost_3)
        self.assertLessEqual(self.cost_3, self.cost_1)

    def test_gt(self) -> None:
        for i in range(1, 4):
            self.assertGreater(self.cost_4, getattr(self, f"cost_{i}"))


class TestNode(TestCase):
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


def get_stops_and_dummy_df(stop_count: int = 3) -> tuple[list, DF]:
    columns = ["lat", "lon",
               "idx", "stop_id", "names",
               "name_cost", "node_cost"]
    stops = [(f"{i}", f"stop_{i}") for i in range(stop_count)]
    lat_lon = [(round(49 + i / 1000, 4), round(9 + i / 1000, 4))
               for i in range(1, 10)]
    costs = [(i, i % 2) for i in range(9, 18)]

    data = [[lat, lon, i, stop_id, name, node_cost, name_cost]
            for i, ((lat, lon), (stop_id, name), (node_cost, name_cost))
            in enumerate(zip(lat_lon, 3 * stops, costs))]
    df = pd.DataFrame(data, columns=columns)
    return stops, df


def get_stops_from_stops_list(stops_list: list[tuple[str, str]]) -> Stops:
    handler = create_handler()
    route = handler.routes.add("test_route")
    for stop_id, stop_name in stops_list:
        stop = GTFSStopEntry(stop_name, stop_id=stop_id)
        handler.stops.entries.append(stop)
    stops = Stops(handler, route.route_id, handler.stops.entries)
    return stops
