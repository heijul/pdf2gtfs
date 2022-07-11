from unittest import TestCase

from src.config import Config
from src.datastructures.gtfs_output.gtfsstop import GTFSStops
from src.datastructures.gtfs_output.stop_times import Time, StopTimes


class TestTime(TestCase):
    def setUp(self) -> None:
        self.t1 = Time(4, 20, 40)
        self.t2 = Time(4, 40, 20)
        self.t3 = Time(5, 55, 1)

    def test_from_string(self):
        Config.time_format = "%H.%M"
        # Seconds can't be set via from_string.
        self.t1.seconds = 0
        self.assertEqual(self.t1, Time.from_string("04.20"))
        self.assertEqual(self.t1, Time.from_string("4.20"))

    def test_eq(self):
        self.assertTrue(self.t1 == self.t1)
        self.assertFalse(self.t1 == self.t2)

    def test_lt(self):
        self.assertTrue(self.t1 < self.t2)
        self.assertFalse(self.t2 < self.t1)
        self.assertFalse(self.t1 < self.t1)

    def test_gt(self):
        self.assertTrue(self.t2 > self.t1)
        self.assertFalse(self.t1 > self.t2)
        self.assertFalse(self.t1 > self.t1)

    def test_le(self):
        self.assertTrue(self.t1 <= self.t1)
        self.assertTrue(self.t1 <= self.t2)
        self.assertFalse(self.t2 <= self.t1)

    def test_copy(self):
        t1c = self.t1.copy()
        self.assertTrue(t1c == self.t1)
        self.assertTrue(t1c.hours == 4)
        self.assertTrue(t1c.minutes == 20)
        t1c.hours = 3
        t1c.minutes = 33
        self.assertTrue(self.t1.hours == 4)
        self.assertTrue(self.t1.minutes == 20)

    def test_add(self):
        t = self.t1 + self.t2
        self.assertEqual(t.hours, 9)
        self.assertEqual(t.minutes, 1)
        self.assertEqual(t.seconds, 0)
        t = self.t1 + self.t3
        self.assertEqual(t.hours, 10)
        self.assertEqual(t.minutes, 15)
        self.assertEqual(t.seconds, 41)

    def test_radd(self):
        self.t1 += self.t2
        self.assertEqual(self.t1.hours, 9)
        self.assertEqual(self.t1.minutes, 1)
        self.assertEqual(self.t1.seconds, 0)
        self.t1 += self.t3
        self.assertEqual(self.t1.hours, 14)
        self.assertEqual(self.t1.minutes, 56)
        self.assertEqual(self.t1.seconds, 1)
        self.t1 += self.t1
        self.assertEqual(self.t1.hours, 29)
        self.assertEqual(self.t1.minutes, 52)
        self.assertEqual(self.t1.seconds, 2)


class TestStopTimes(TestCase):
    def setUp(self) -> None:
        self.trip_id = 1
        self.stop_times = StopTimes()

        self.stops = GTFSStops()
        for stop_name in "ABC":
            self.stops.add(stop_name)

    def test_add_multiple(self):
        self.skipTest("Not implemented yet...")

        # TODO: Easier to test with actual data
        stops = self.stops.entries
        times = {stops[0]: "23.29", stops[1]: "23.47", stops[2]: "00.13"}
        self.assertTrue(len(self.stop_times.entries) == 0)
        self.stop_times.add_multiple(0, self.stops, 0, times)
        self.assertTrue(len(self.stop_times.entries) == 1)
        times = {stops[0]: "23.42", stops[1]: "00.00", stops[2]: "00.26"}
        self.stop_times.add_multiple(0, self.stops, 0, times)
        self.assertTrue(len(self.stop_times.entries) == 2)
        times = {stops[0]: "00.14", stops[1]: "00.15", stops[2]: "00.16"}
        self.stop_times.add_multiple(0, self.stops, 1, times)
        self.assertTrue(len(self.stop_times.entries) == 3)
        self.assertTrue(self.stop_times.entries[0].arrival_time <
                        self.stop_times.entries[1].arrival_time)
        self.assertTrue(self.stop_times.entries[1].arrival_time <
                        self.stop_times.entries[2].arrival_time)
