from dataclasses import fields

import pandas as pd

from config import Config
from datastructures.gtfs_output.stop import GTFSStops
from datastructures.gtfs_output.stop_times import (
    get_repeat_deltas, GTFSStopTimes, GTFSStopTimesEntry, Time)
from datastructures.gtfs_output.trips import GTFSTrips
from test import P2GTestCase
from test_datastructures.test_gtfs_output import GTFSOutputBaseClass
from test_datastructures.test_timetable import create_stops


class TestTime(P2GTestCase):
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

    def test_from_gtfs(self) -> None:
        self.assertEqual(self.t1, Time.from_gtfs("04:20:40"))
        self.assertEqual(self.t2, Time.from_gtfs("04:40:20"))
        self.assertEqual(self.t3, Time.from_gtfs("05:55:01"))

    def test_to_output(self) -> None:
        self.assertEqual("04:20:40", self.t1.to_output())
        self.assertEqual("04:40:20", self.t2.to_output())
        self.assertEqual("05:55:01", self.t3.to_output())

    def test_copy(self) -> None:
        t1c = self.t1.copy()
        self.assertTrue(t1c == self.t1)
        self.assertTrue(t1c.hours == 4)
        self.assertTrue(t1c.minutes == 20)
        t1c.hours = 3
        t1c.minutes = 33
        self.assertTrue(self.t1.hours == 4)
        self.assertTrue(self.t1.minutes == 20)

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

    def test_to_hours(self) -> None:
        self.assertAlmostEqual(4.3444444, self.t1.to_hours())
        self.assertAlmostEqual(4.6722222, self.t2.to_hours())
        self.assertAlmostEqual(5.9169444, self.t3.to_hours())
        self.assertEqual(self.t1, Time.from_hours(self.t1.to_hours()))
        self.assertEqual(self.t2, Time.from_hours(self.t2.to_hours()))
        self.assertEqual(self.t3, Time.from_hours(self.t3.to_hours()))

    def test_from_hours(self) -> None:
        self.assertEqual(self.t1, Time.from_hours(self.t1.to_hours()))
        self.assertEqual(self.t2, Time.from_hours(self.t2.to_hours()))
        self.assertEqual(self.t3, Time.from_hours(self.t3.to_hours()))

    def test_from_minutes(self) -> None:
        self.assertEqual(self.t1, Time.from_minutes(60 * self.t1.to_hours()))
        self.assertEqual(self.t2, Time.from_minutes(60 * self.t2.to_hours()))
        self.assertEqual(self.t3, Time.from_minutes(60 * self.t3.to_hours()))


class TestGTFSStopTimesEntry(P2GTestCase):
    def test_duplicate(self) -> None:
        s1 = GTFSStopTimesEntry("trip id 1", "stop id 1", 0,
                                Time(13, 45, 22), Time(13, 49, 4))
        s2 = s1.duplicate("trip id 2")
        self.assertNotEqual(s1, s2)
        s2.trip_id = s1.trip_id
        self.assertEqual(s1, s2)

    def test_from_series(self) -> None:
        index = [f.name for f in fields(GTFSStopTimesEntry)]
        values = ["trip 1", "13:55:00", "14:01:10", "stop 1", "33"]
        entry = GTFSStopTimesEntry.from_series(pd.Series(values, index=index))
        self.assertEqual(values[0], entry.trip_id)
        self.assertEqual(Time(13, 55, 0), entry.arrival_time)
        self.assertEqual(Time(14, 1, 10), entry.departure_time)
        self.assertEqual("stop 1", entry.stop_id)
        self.assertEqual(33, entry.stop_sequence)
        # Times greater 24 h should work.
        values = ["trip 1", "24:55:00", "24:55:10", "stop 1", "33"]
        entry = GTFSStopTimesEntry.from_series(pd.Series(values, index=index))
        self.assertEqual(values[0], entry.trip_id)
        self.assertEqual(Time(24, 55), entry.arrival_time)
        self.assertEqual(Time(24, 55, 10), entry.departure_time)
        self.assertEqual("stop 1", entry.stop_id)
        self.assertEqual(33, entry.stop_sequence)

    def test__comparisons__(self) -> None:
        s1 = GTFSStopTimesEntry("trip id 1", "stop id 1", 0,
                                Time(13, 45, 22), Time(13, 49, 4))
        s2 = GTFSStopTimesEntry("trip id 1", "stop id 1", 0,
                                Time(13, 45, 22), Time(13, 49, 5))
        s3 = GTFSStopTimesEntry("trip id 1", "stop id 1", 0,
                                Time(13, 45, 23), Time(13, 49, 4))
        s4 = GTFSStopTimesEntry("trip id 1", "stop id 1", 1,
                                Time(13, 45, 22), Time(13, 49, 4))
        s5 = GTFSStopTimesEntry("trip id 1", "stop id 2", 0,
                                Time(13, 45, 22), Time(13, 49, 4))
        s6 = GTFSStopTimesEntry("trip id 2", "stop id 1", 0,
                                Time(13, 45, 22), Time(13, 49, 4))
        s7 = GTFSStopTimesEntry("trip id 1", "stop id 1", 0,
                                Time(13, 45, 22), Time(13, 49, 4))
        self.assertNotEqual(s1, s2)
        self.assertNotEqual(s1, s3)
        self.assertNotEqual(s1, s4)
        self.assertNotEqual(s1, s5)
        self.assertNotEqual(s1, s6)
        self.assertEqual(s1, s7)


class TestGTFSStopTimes(GTFSOutputBaseClass):
    def setUp(self) -> None:
        self.trip_id = 1
        self.stop_times = GTFSStopTimes(self.temp_path)

        self.stops = create_stops(3)

        self.gtfs_stops = GTFSStops(self.temp_path)
        for stop in self.stops:
            self.gtfs_stops.add(stop.name)

    def test_add(self) -> None:
        t1 = Time(17, 58, 31)
        t2 = Time(18, 3, 20)
        self.assertEqual(0, len(self.stop_times))
        e1 = self.stop_times.add("trip 1", "stop 1", 0, t1)
        self.assertEqual(1, len(self.stop_times))
        e2 = self.stop_times.add("trip 1", "stop 1", 0, t1)
        self.assertEqual(1, len(self.stop_times))
        self.assertEqual(e1, e2)
        e3 = self.stop_times.add("trip 1", "stop 1", 0, t1, t2)
        self.assertEqual(2, len(self.stop_times))
        self.assertEqual(e1.arrival_time, e3.arrival_time)
        self.assertNotEqual(e1.departure_time, e3.departure_time)

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

    def test_merge(self) -> None:
        stop_times_1 = GTFSStopTimes(self.temp_path)
        times = {self.stops[0]: "23.29",
                 self.stops[1]: "23.47",
                 self.stops[2]: "00.13"}
        stop_times_1.add_multiple("0", self.gtfs_stops, 0, times)
        stop_times_2 = GTFSStopTimes(self.temp_path)
        times = {self.stops[0]: "00.14",
                 self.stops[1]: "00.15",
                 self.stops[2]: "00.16"}
        stop_times_2.add_multiple("0", self.gtfs_stops, 1, times)
        self.assertEqual(3, len(stop_times_1))
        self.assertEqual(3, len(stop_times_2))
        self.stop_times.merge(stop_times_2)
        self.assertEqual(3, len(self.stop_times))
        self.assertEqual(stop_times_2.entries, self.stop_times.entries)
        self.stop_times.merge(stop_times_1)
        self.assertEqual(6, len(self.stop_times))
        self.assertEqual(stop_times_2.entries + stop_times_1.entries,
                         self.stop_times.entries)

    def test_duplicate_with_trip_id(self) -> None:
        times = {self.stops[0]: "23.42",
                 self.stops[1]: "00.00",
                 self.stops[2]: "00.26"}
        self.stop_times.add_multiple("0", self.gtfs_stops, 0, times)
        stop_times = self.stop_times._duplicate_with_trip_id("7")
        self.assertEqual(len(self.stop_times.entries), len(stop_times.entries))
        # Equal except trip_id and entry_id.
        zipper = zip(self.stop_times, stop_times, strict=True)
        for i, (entry1, entry2) in enumerate(zipper):
            entry1: GTFSStopTimesEntry
            entry2: GTFSStopTimesEntry
            with self.subTest(i=i):
                self.assertEqual(entry1.stop_id, entry2.stop_id)
                self.assertEqual(entry1.stop_sequence, entry2.stop_sequence)
                self.assertEqual("0", entry1.trip_id)
                self.assertEqual("7", entry2.trip_id)
                self.assertEqual(entry1.arrival_time, entry2.arrival_time)
                self.assertEqual(entry1.departure_time, entry2.departure_time)

        times = {self.stops[0]: "00.14",
                 self.stops[1]: "00.15",
                 self.stops[2]: "00.16"}
        self.stop_times.add_multiple("1", self.gtfs_stops, 0, times)
        stop_times = self.stop_times._duplicate_with_trip_id("7")
        self.assertEqual(len(self.stop_times.entries), len(stop_times.entries))
        # Equal except trip_id and entry_id.
        zipper = zip(self.stop_times, stop_times, strict=True)
        for i, (entry1, entry2) in enumerate(zipper):
            entry1: GTFSStopTimesEntry
            entry2: GTFSStopTimesEntry
            with self.subTest(i=i):
                self.assertEqual(entry1.stop_id, entry2.stop_id)
                self.assertEqual(entry1.stop_sequence, entry2.stop_sequence)
                self.assertIn(entry1.trip_id, ["0", "1"])
                self.assertEqual("7", entry2.trip_id)
                self.assertEqual(entry1.arrival_time, entry2.arrival_time)
                self.assertEqual(entry1.departure_time, entry2.departure_time)

    def test_shift(self) -> None:
        times = {self.stops[0]: "23.42",
                 self.stops[1]: "00.00",
                 self.stops[2]: "00.26"}
        self.stop_times.add_multiple("0", self.gtfs_stops, 0, times)
        times = {self.stops[0]: "00.14",
                 self.stops[1]: "00.15",
                 self.stops[2]: "00.16"}
        self.stop_times.add_multiple("1", self.gtfs_stops, 0, times)
        times = [(st.arrival_time, st.departure_time)
                 for st in self.stop_times.entries]
        delta = Time(1, 7, 3)
        self.stop_times.shift(delta)
        for i, entry in enumerate(self.stop_times):
            with self.subTest(i=i):
                arr_time, dep_time = times[i]
                self.assertEqual(arr_time + delta, entry.arrival_time)
                self.assertEqual(dep_time + delta, entry.departure_time)

    def test_add_repeat(self) -> None:
        times = {self.stops[0]: "00.42",
                 self.stops[1]: "01.00",
                 self.stops[2]: "01.26"}
        stop_times1 = GTFSStopTimes(self.temp_path)
        stop_times1.add_multiple("0", self.gtfs_stops, 0, times)
        times = {self.stops[0]: "07.24",
                 self.stops[1]: "07.25",
                 self.stops[2]: "07.26"}
        stop_times2 = GTFSStopTimes(self.temp_path)
        stop_times2.add_multiple("1", self.gtfs_stops, 0, times)
        trips = GTFSTrips(self.temp_path)
        trip_factory = trips.get_factory("service_1", "route_id 1")
        entries = GTFSStopTimes.add_repeat(
            stop_times1, stop_times2, [30], trip_factory)
        self.assertEqual(13, len(entries))
        prev = entries[0]
        for entry in entries[1:]:
            self.assertGreater(entry, prev)
            self.assertLess(entry, stop_times2)
            prev = entry

    def test__get_entry_from_stop_id(self) -> None:
        times = {self.stops[0]: "23.42",
                 self.stops[1]: "00.00",
                 self.stops[2]: "00.26"}
        entries = self.stop_times.add_multiple("0", self.gtfs_stops, 0, times)
        for i, entry1 in enumerate(entries):
            with self.subTest(i=i):
                stop_id = self.gtfs_stops.entries[i].stop_id
                entry2 = self.stop_times._get_entry_from_stop_id(stop_id)
                self.assertEqual(entry1, entry2)

    def test__comparisons__(self) -> None:
        stop_times1 = GTFSStopTimes(self.temp_path)
        times = {self.stops[0]: "22.42",  # 23.42
                 self.stops[1]: "23.00",  # 00.00
                 self.stops[2]: "23.26"}  # 00.26
        stop_times1.add_multiple("0", self.gtfs_stops, 0, times)
        stop_times2 = GTFSStopTimes(self.temp_path)
        times = {self.stops[0]: "00.14",
                 self.stops[1]: "00.15",
                 self.stops[2]: "00.36"}
        stop_times2.add_multiple("1", self.gtfs_stops, 0, times)
        stop_times3 = GTFSStopTimes(self.temp_path)
        times = {self.stops[0]: "10.14",
                 self.stops[1]: "10.15",
                 self.stops[2]: "10.36"}
        stop_times3.add_multiple("1", self.gtfs_stops, 0, times)
        self.assertLess(stop_times2, stop_times3)
        self.assertGreater(stop_times1, stop_times2)
        self.assertLessEqual(stop_times2, stop_times2)
        self.assertGreaterEqual(stop_times2, stop_times2)
        # TODO: Test with different stop lengths.
        # TODO: Needs fix for st3 > st1 (see comments)

    def test_get_with_stop_id(self) -> None:
        times = {self.stops[0]: "23.42",
                 self.stops[1]: "00.00",
                 self.stops[2]: "00.26"}
        self.stop_times.add_multiple("0", self.gtfs_stops, 0, times)
        times = {self.stops[0]: "05.14",
                 self.stops[1]: "05.15",
                 self.stops[2]: "05.16"}
        self.stop_times.add_multiple("1", self.gtfs_stops, 0, times)

        stop_id = self.gtfs_stops.entries[1].stop_id
        trip_ids = ["1"]
        entries = self.stop_times.get_with_stop_id(trip_ids, stop_id)
        self.assertEqual(1, len(entries))
        for i, entry in enumerate(entries):
            with self.subTest(i=i):
                self.assertIn(entry.trip_id, trip_ids)
                self.assertEqual(stop_id, entry.stop_id)

        trip_ids = ["1", "0"]
        stop_id = self.gtfs_stops.entries[2].stop_id
        entries = self.stop_times.get_with_stop_id(trip_ids, stop_id)
        self.assertEqual(2, len(entries))
        for i, entry in enumerate(entries):
            with self.subTest(i=i):
                self.assertIn(entry.trip_id, trip_ids)
                self.assertEqual(stop_id, entry.stop_id)
        # Not all trips need to be present.
        trip_ids += ["666"]
        self.assertEqual(entries,
                         self.stop_times.get_with_stop_id(trip_ids, stop_id))
        # No stop_time with the given trip_ids exist.
        trip_ids = ["666"]
        entries = self.stop_times.get_with_stop_id(trip_ids, stop_id)
        self.assertEqual(0, len(entries))
        self.assertFalse(
            any([e.trip_id in trip_ids for e in self.stop_times.entries]))

    def test_get_with_trip_id(self) -> None:
        times = {self.stops[0]: "23.42",
                 self.stops[1]: "00.00",
                 self.stops[2]: "00.26"}
        self.stop_times.add_multiple("0", self.gtfs_stops, 0, times)
        times = {self.stops[0]: "05.14",
                 self.stops[1]: "05.15",
                 self.stops[2]: "05.16"}
        self.stop_times.add_multiple("1", self.gtfs_stops, 0, times)

        entries = self.stop_times.get_with_trip_id("0")
        self.assertEqual(3, len(entries))
        for i, entry in enumerate(entries):
            with self.subTest(i=i):
                self.assertEqual("0", entry.trip_id)

        entries = self.stop_times.get_with_trip_id("1")
        self.assertEqual(3, len(entries))
        for i, entry in enumerate(entries):
            with self.subTest(i=i):
                self.assertEqual("1", entry.trip_id)


class Test(P2GTestCase):
    def test__get_repeat_deltas(self) -> None:
        def get_five_deltas(cycle) -> list[Time]:
            five_deltas = []
            while len(five_deltas) < 5:
                five_deltas.append(next(cycle))
            return five_deltas

        deltas = [7]
        Config.repeat_strategy = "mean"
        repeat_deltas = get_repeat_deltas(deltas)
        result = [Time(minutes=7)] * 5
        self.assertEqual(result, get_five_deltas(repeat_deltas))
        Config.repeat_strategy = "cycle"
        repeat_deltas = get_repeat_deltas(deltas)
        self.assertEqual(result, get_five_deltas(repeat_deltas))
        deltas = [7, 8]
        Config.repeat_strategy = "mean"
        repeat_deltas = get_repeat_deltas(deltas)
        result = [Time.from_minutes(7.5)] * 5
        self.assertEqual(result, get_five_deltas(repeat_deltas))
        Config.repeat_strategy = "cycle"
        repeat_deltas = get_repeat_deltas(deltas)
        result = [Time.from_minutes(7), Time.from_minutes(8),
                  Time.from_minutes(7), Time.from_minutes(8),
                  Time.from_minutes(7)]
        self.assertEqual(result, get_five_deltas(repeat_deltas))
