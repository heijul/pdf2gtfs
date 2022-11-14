from pathlib import Path
from unittest import TestCase

from config import Config
from datastructures.gtfs_output.stop import GTFSStops
from datastructures.gtfs_output.stop_times import GTFSStopTimes, Time
from test_datastructures.test_timetable import create_stops


class TestTime(TestCase):
    def setUp(self) -> None:
        self.t1 = Time(4, 20, 40)
        self.t2 = Time(4, 40, 20)
        self.t3 = Time(5, 55, 1)

    def test_from_string(self) -> None:
        Config.time_format = "%H.%M"
        # Seconds can't be set via from_string.
        self.t1.seconds = 0
        self.assertEqual(self.t1, Time.from_string("04.20"))
        self.assertEqual(self.t1, Time.from_string("4.20"))

    def test_eq(self) -> None:
        self.assertTrue(self.t1 == self.t1)
        self.assertFalse(self.t1 == self.t2)

    def test_lt(self) -> None:
        self.assertTrue(self.t1 < self.t2)
        self.assertFalse(self.t2 < self.t1)
        self.assertFalse(self.t1 < self.t1)

    def test_gt(self) -> None:
        self.assertTrue(self.t2 > self.t1)
        self.assertFalse(self.t1 > self.t2)
        self.assertFalse(self.t1 > self.t1)

    def test_le(self) -> None:
        self.assertTrue(self.t1 <= self.t1)
        self.assertTrue(self.t1 <= self.t2)
        self.assertFalse(self.t2 <= self.t1)

    def test_copy(self) -> None:
        t1c = self.t1.copy()
        self.assertTrue(t1c == self.t1)
        self.assertTrue(t1c.hours == 4)
        self.assertTrue(t1c.minutes == 20)
        t1c.hours = 3
        t1c.minutes = 33
        self.assertTrue(self.t1.hours == 4)
        self.assertTrue(self.t1.minutes == 20)

    def test_add(self) -> None:
        t = self.t1 + self.t2
        self.assertEqual(t.hours, 9)
        self.assertEqual(t.minutes, 1)
        self.assertEqual(t.seconds, 0)
        t = self.t1 + self.t3
        self.assertEqual(t.hours, 10)
        self.assertEqual(t.minutes, 15)
        self.assertEqual(t.seconds, 41)

    def test_radd(self) -> None:
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
        dummy_dir = Path("")
        self.trip_id = 1
        self.stop_times = GTFSStopTimes(dummy_dir)

        self.stops = create_stops(3)

        self.gtfs_stops = GTFSStops(dummy_dir)
        for stop in self.stops:
            self.gtfs_stops.add(stop.name)

    def test_add_multiple(self) -> None:
        times = {self.stops[0]: "23.29",
                 self.stops[1]: "23.47",
                 self.stops[2]: "00.13"}
        self.assertEqual(0, len(self.stop_times.entries))
        self.stop_times.add_multiple("0", self.gtfs_stops, 0, times)
        self.assertEqual(3, len(self.stop_times.entries))
        times = {self.stops[0]: "23.42",
                 self.stops[1]: "00.00",
                 self.stops[2]: "00.26"}
        self.stop_times.add_multiple("0", self.gtfs_stops, 0, times)
        self.assertTrue(6, len(self.stop_times.entries))
        times = {self.stops[0]: "00.14",
                 self.stops[1]: "00.15",
                 self.stops[2]: "00.16"}
        self.stop_times.add_multiple("0", self.gtfs_stops, 1, times)
        self.assertTrue(9, len(self.stop_times.entries))
        self.assertTrue(self.stop_times.entries[0].arrival_time <
                        self.stop_times.entries[1].arrival_time)
        self.assertTrue(self.stop_times.entries[1].arrival_time <
                        self.stop_times.entries[2].arrival_time)
