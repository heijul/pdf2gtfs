from unittest import mock

from config import Config
from datastructures.gtfs_output.stop_times import Time
from test_locate.test_finder import get_stops_from_stops_list
from test import P2GTestCase


class TestHelper(P2GTestCase):
    def test_get_travel_distance(self) -> None:
        # TODO: Ignore for now cause we'd need a working handler + stop_times
        pass


class TestStop(P2GTestCase):
    def setUp(self) -> None:
        stop_list = [("0", "stop_0"), ("1", "stop_1")]
        self.stops = get_stops_from_stops_list(stop_list)
        Config.average_speed = 15

    def test_exists(self) -> None:
        ...

    def test_is_first(self) -> None:
        ...

    def test_is_last(self) -> None:
        ...

    def test_next(self) -> None:
        ...

    @mock.patch("locate.finder.stops.Stops.get_avg_time_between")
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
