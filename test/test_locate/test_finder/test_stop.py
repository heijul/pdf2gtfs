from unittest import mock

import pandas as pd

from pdf2gtfs.config import Config
from pdf2gtfs.datastructures.gtfs_output.stop_times import Time
from pdf2gtfs.locate import Location
from pdf2gtfs.locate.finder.cost import Cost
from pdf2gtfs.locate.finder.loc_nodes import ENode, MNode, Node, Nodes
from pdf2gtfs.locate.finder.stops import Stops
from test import P2GTestCase
from test.test_locate.test_finder import get_stops_from_stops_list


class TestHelper(P2GTestCase):
    def test_get_travel_distance(self) -> None:
        pass


class TestStop(P2GTestCase):
    def setUp(self) -> None:
        stop_list = [(f"{i}", f"stop_{i}") for i in range(5)]
        self.stops: Stops = get_stops_from_stops_list(stop_list)
        Config.average_speed = 15
        values = [[i, i, f"stop_{i}", i, f"{i}", i, i] for i in range(10)]
        df = pd.DataFrame(values,
                          columns=["lat", "lon", "names", "node_cost",
                                   "stop_id", "idx", "name_cost"])
        self.nodes = Nodes(df, self.stops)

    def test_exists(self) -> None:
        for i, stop in enumerate(self.stops.stops):
            with self.subTest(i=i):
                self.assertFalse(stop.exists)
        stop = self.stops.stops[0]
        args = (1, "stop", Location(33.21, 12.32), Cost(0, 0, 0, 0))
        Node(stop, *args)
        self.assertFalse(stop.exists)
        stop = self.stops.stops[1]
        MNode(stop, *args[:-1], 0)
        self.assertFalse(stop.exists)
        stop = self.stops.stops[2]
        ENode(stop, args[2], 0)
        self.assertTrue(stop.exists)

    def test_is_first(self) -> None:
        self.assertTrue(self.stops.stops[0].is_first)
        for i, stop in enumerate(self.stops.stops[1:]):
            with self.subTest(i=i):
                self.assertFalse(stop.is_first)

    def test_is_last(self) -> None:
        self.assertTrue(self.stops.stops[-1].is_last)
        for i, stop in enumerate(self.stops.stops[:-1]):
            with self.subTest(i=i):
                self.assertFalse(stop.is_last)

    def test_next(self) -> None:
        next_stop = self.stops.last
        for i, current in enumerate(reversed(self.stops.stops[:-1])):
            if current.is_last:
                break
            with self.subTest(i=i):
                self.assertEqual(next_stop, current.next)
                next_stop = current

    @mock.patch("pdf2gtfs.locate.finder.stops.Stops.get_avg_time_between")
    def test__get_distance_bounds(self, get_avg_time_between) -> None:
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


class TestStops(P2GTestCase):
    def test_stops(self) -> None:
        ...

    def test__create_stops(self) -> None:
        ...

    def test_get_avg_time_between(self) -> None:
        ...

    def test_get_from_stop_id(self) -> None:
        ...
