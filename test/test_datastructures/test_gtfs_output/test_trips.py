from dataclasses import fields

import pandas as pd

from pdf2gtfs.datastructures.gtfs_output.stop_times import GTFSStopTimes, Time
from pdf2gtfs.datastructures.gtfs_output.trips import GTFSTrips, GTFSTripsEntry
from test import P2GTestCase
from test.test_datastructures.test_gtfs_output import GTFSOutputBaseClass


class TestGTFSTripEntry(P2GTestCase):
    def test_from_series(self) -> None:
        index = [f.name for f in fields(GTFSTripsEntry)]
        values = ["trip_id", "route_id", "service_id 1"]
        entry = GTFSTripsEntry.from_series(pd.Series(values, index=index))
        self.assertEqual(values[0], entry.trip_id)
        self.assertEqual(values[1], entry.route_id)
        self.assertEqual(values[2], entry.service_id)


class TestGTFSTrips(GTFSOutputBaseClass):
    def setUp(self) -> None:
        self.trips = GTFSTrips(self.temp_path)

    def test_add(self) -> None:
        self.assertEqual(0, len(self.trips))
        e1 = self.trips.add("route 1", "service 1")
        self.assertEqual(1, len(self.trips))
        e2 = self.trips.add("route 1", "service 1")
        self.assertEqual(2, len(self.trips))
        self.assertNotEqual(e1.trip_id, e2.trip_id)
        self.trips.add("route 2", "service 1")
        self.assertEqual(3, len(self.trips))
        self.trips.add("route 2", "service 2")
        self.assertEqual(4, len(self.trips))

    def test_remove(self) -> None:
        e1 = self.trips.add("route 1", "service 1")
        e2 = self.trips.add("route 1", "service 2")
        self.assertEqual(2, len(self.trips))
        self.trips.remove(e1)
        self.assertEqual(1, len(self.trips))
        self.trips.remove(e1)
        self.assertEqual(1, len(self.trips))
        self.trips.remove(e2)
        self.assertEqual(0, len(self.trips))
        # Readding works, but id is updated.
        e3 = self.trips.add("route 1", "service 1")
        self.assertEqual(1, len(self.trips))
        self.assertNotEqual(e1, e3)

    def test_get_factory(self) -> None:
        factory1 = self.trips.get_factory("service 1", "route 1")
        factory2 = self.trips.get_factory("service 1", "route 2")
        self.assertEqual(0, len(self.trips))
        factory1()
        self.assertEqual(1, len(self.trips))
        factory1()
        factory2()
        factory2()
        factory1()
        self.assertEqual(5, len(self.trips))
        self.assertEqual(3, len(self.trips.get_with_route_id("route 1")))
        self.assertEqual(2, len(self.trips.get_with_route_id("route 2")))

    def test_remove_unused(self) -> None:
        stop_times = GTFSStopTimes(self.temp_path)

        e1 = self.trips.add("route 1", "service 1")
        e2 = self.trips.add("route 2", "service 1")
        e3 = self.trips.add("route 3", "service 3")

        stop_times.add(e1.trip_id, "stop 0", 0, Time(0, 1, 0))
        stop_times.add(e2.trip_id, "stop 1", 1, Time(0, 2, 0))
        stop_times.add(e2.trip_id, "stop 0", 0, Time(0, 1, 0))
        self.assertIn(e1, self.trips.entries)
        self.assertIn(e2, self.trips.entries)
        self.assertIn(e3, self.trips.entries)
        self.trips.remove_unused(stop_times)
        self.assertIn(e1, self.trips.entries)
        self.assertIn(e2, self.trips.entries)
        self.assertNotIn(e3, self.trips.entries)

    def test_get_with_route_id(self) -> None:
        factory1 = self.trips.get_factory("service 1", "route 1")
        e1 = factory1()
        e2 = factory1()
        e3 = factory1()
        self.assertEqual([], self.trips.get_with_route_id("route 0"))
        self.assertEqual(3, len(self.trips.get_with_route_id("route 1")))
        self.trips.remove(e1)
        self.trips.remove(e2)
        self.trips.remove(e3)
        self.assertEqual([], self.trips.get_with_route_id("route 1"))
