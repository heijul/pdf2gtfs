from typing import TypeAlias
from unittest import TestCase

import numpy as np
import pandas as pd

from config import Config
from datastructures.gtfs_output.handler import GTFSHandler
from datastructures.gtfs_output.stop_times import Time
from finder.cost import Cost
from finder.location_nodes import Nodes
from finder.stops import Stop, Stops


DF: TypeAlias = pd.DataFrame


class TestStop(TestCase):
    def setUp(self) -> None:
        self.stop_1 = Stop(0, "0", "stop_0", None, 0)
        self.stop_2 = Stop(1, "1", "stop_1", None, 0)
        self.stop_3 = Stop(2, "2", "stop_2", None, 0)
        Config.average_speed = 15

    def test__set_distance_bounds(self) -> None:
        times = [1, 2, 12, 0]
        expected_lower = [0, 250, 2750, 0]
        expected_upper = [500, 750, 3250, 0]
        for i in range(3):
            self.stop_1._avg_time_to_next = Time(minutes=times[i])
            self.stop_1._set_distance_bounds()
            lower, upper = self.stop_1.distance_bounds
            self.assertEqual(expected_lower[i], lower.m)
            self.assertEqual(expected_upper[i], upper.m)

    def test_get_max_dist(self) -> None:
        minute = Time(minutes=1)
        max_dist = self.stop_1.get_max_dist(minute)
        self.assertEqual(250, max_dist.m)
        no_time = Time()
        max_dist = self.stop_1.get_max_dist(no_time)
        self.assertEqual(0, max_dist.m)
        hour = Time(hours=1)
        max_dist = self.stop_1.get_max_dist(hour)
        self.assertEqual(15, max_dist.km)
        fifty_five = Time(minutes=56)
        max_dist = self.stop_1.get_max_dist(fifty_five)
        self.assertEqual(14, max_dist.km)
        fifty_five = Time(minutes=56)
        max_dist = self.stop_1.get_max_dist(fifty_five)
        self.assertEqual(14, max_dist.km)

    def test_max_dist_to_next(self) -> None:
        self.stop_1._avg_time_to_next = Time(minutes=3)
        self.stop_1.next = self.stop_2
        max_dist = self.stop_1.max_dist_to_next
        self.assertEqual(750, max_dist.m)

    def test_before(self) -> None:
        self.assertTrue(self.stop_1.before(self.stop_2))
        self.assertFalse(self.stop_2.before(self.stop_1))
        self.assertTrue(self.stop_1.before(self.stop_3))
        self.assertFalse(self.stop_2.before(self.stop_2))

    def test_after(self) -> None:
        self.assertFalse(self.stop_1.after(self.stop_2))
        self.assertTrue(self.stop_2.after(self.stop_1))
        self.assertTrue(self.stop_3.after(self.stop_1))
        self.assertFalse(self.stop_2.after(self.stop_2))

    def test_avg_time_to_next(self) -> None:
        # TODO: Ignore for now cause we'd need a working handler + stop_times
        pass


class TestCost(TestCase):
    def setUp(self) -> None:
        self.cost_1 = Cost(1, 2, 3, 4, 5)
        self.cost_2 = Cost(5, 4, 3, 2, 1)
        self.cost_3 = Cost(1, 2, 3, 4, 5)
        self.cost_4 = Cost(4, 4, 4, 4, 4)

    def test_from_cost(self) -> None:
        self.assertNotEqual(id(self.cost_1), id(Cost.from_cost(self.cost_1)))
        self.assertEqual(self.cost_1, Cost.from_cost(self.cost_1))
        self.assertEqual(self.cost_2, Cost.from_cost(self.cost_2))
        self.assertEqual(self.cost_3, Cost.from_cost(self.cost_3))

        self.assertEqual(self.cost_3, Cost.from_cost(self.cost_1))

    def test_eq(self) -> None:
        self.assertEqual(self.cost_1, self.cost_1)
        self.assertEqual(self.cost_1, self.cost_3)
        self.assertEqual(self.cost_3, self.cost_1)
        self.assertNotEqual(self.cost_1, self.cost_4)

        self.assertEqual(self.cost_3, self.cost_2)
        self.assertNotEqual(self.cost_3.costs, self.cost_2.costs)

    def test_lt(self) -> None:
        self.assertLess(self.cost_1, self.cost_4)
        self.assertLess(self.cost_2, self.cost_4)

    def test_le(self) -> None:
        self.assertLessEqual(self.cost_1, self.cost_2)
        self.assertLessEqual(self.cost_2, self.cost_1)
        self.assertLessEqual(self.cost_2, self.cost_3)
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
        nodes = self.nodes.node_heap

        for node in nodes:
            if node.stop == self.stops.last:
                continue
            neighbors = list(node.get_neighbors())
            # Check that the neighbors are close
            for neigbor in neighbors:
                self.assertTrue(node.is_close(np.array(list(neigbor.loc))))
            # Check that neighbors all have the correct stop.
            for neighbor in neighbors:
                self.assertEqual(node.stop.next, neighbor.stop)

    def test_update_parent_if_lower_cost(self) -> None:
        # TODO:
        pass


def get_stops_and_dummy_df(stop_count: int = 3) -> tuple[list, DF]:
    columns = ["lat", "lon",
               "idx", "stop_id", "names",
               "name_cost", "node_cost"]
    stops = [(f"{i}", f"stop_{i}") for i in range(stop_count)]
    lat_lon = [(round(49 + i / 1000, 4), round(9 + i/1000, 4))
               for i in range(1, 10)]
    costs = [(i, i % 2) for i in range(9, 18)]

    data = [[lat, lon, i, stop_id, name, node_cost, name_cost]
            for i, ((lat, lon), (stop_id, name), (node_cost, name_cost))
            in enumerate(zip(lat_lon, 3 * stops, costs))]
    df = pd.DataFrame(data, columns=columns)
    return stops, df


def get_stops_from_stops_list(stops_list: list[tuple[str, str]]) -> Stops:
    stops = Stops(GTFSHandler(), stops_list)
    for i, stop in enumerate(stops):
        stop._avg_time_to_next = Time(minutes=i + 3)
    return stops
