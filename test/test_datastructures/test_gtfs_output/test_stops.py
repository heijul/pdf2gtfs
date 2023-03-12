from dataclasses import fields

import pandas as pd

from pdf2gtfs.config import Config
from pdf2gtfs.datastructures.gtfs_output.stop import (
    GTFSStopEntry, GTFSStops,
    WHEELCHAIR_TO_INT, WheelchairBoarding)
from test.test_datastructures.test_gtfs_output import GTFSOutputBaseClass


class TestGTFSStopEntry(GTFSOutputBaseClass):
    def test_valid(self) -> None:
        s = GTFSStopEntry("")
        self.assertFalse(s.valid)
        s.stop_lat = 3
        self.assertFalse(s.valid)
        s.stop_lon = 3
        self.assertFalse(s.valid)
        s.stop_name = "test stop a"
        self.assertTrue(s.valid)
        s.stop_lon = None
        self.assertFalse(s.valid)
        s.stop_lon = 48
        s.stop_lat = None
        self.assertFalse(s.valid)

    def test_set_location(self) -> None:
        Config.interpolate_missing_locations = True
        s1 = GTFSStopEntry("stop 1")
        self.assertFalse(s1.valid)
        s1.set_location(3, 3, True)
        self.assertTrue(s1.valid)
        s2 = GTFSStopEntry("stop 2")
        self.assertFalse(s2.valid)
        s2.set_location(45, 12, False)
        self.assertTrue(s2.valid)
        # If we do not interpolate, missing locations should not be added.
        Config.interpolate_missing_locations = False
        s3 = GTFSStopEntry("stop 3")
        self.assertFalse(s3.valid)
        s3.set_location(3, 3, True)
        self.assertFalse(s3.valid)

        s2.set_location(None, 12, False)
        self.assertFalse(s2.valid)
        s2.set_location(45, 12, False)
        self.assertTrue(s2.valid)
        s2.set_location(12, None, False)
        self.assertFalse(s2.valid)
        s2.set_location(45, 12, False)
        self.assertTrue(s2.valid)

    def test_get_field_value(self) -> None:
        s = GTFSStopEntry("stop 1", "stop 1 id")
        stop_fields = fields(s)
        self.assertEqual("stop 1 id", s.get_field_value(stop_fields[0]))
        self.assertEqual("stop 1", s.get_field_value(stop_fields[1]))
        self.assertEqual(None, s.get_field_value(stop_fields[2]))
        self.assertEqual(None, s.get_field_value(stop_fields[3]))
        self.assertEqual("", s.get_field_value(stop_fields[4]))
        s.set_location(23.3, 31.12, False)
        self.assertEqual(23.3, s.get_field_value(stop_fields[2]))
        self.assertEqual(31.12, s.get_field_value(stop_fields[3]))
        self.assertEqual("", s.get_field_value(stop_fields[4]))
        s.set_location(23.3, 31.12, True)
        self.assertNotEqual("", s.get_field_value(stop_fields[4]))

    def test_from_series(self) -> None:
        index = [f.name for f in fields(GTFSStopEntry)]
        values = ["stop_id_1", "stop 1", "32.31", "-12.98", "testdesc", "1"]
        entry = GTFSStopEntry.from_series(pd.Series(values, index=index))
        self.assertEqual(values[0], entry.stop_id)
        self.assertEqual(values[1], entry.stop_name)
        self.assertEqual(float(values[2]), entry.stop_lat)
        self.assertEqual(float(values[3]), entry.stop_lon)
        self.assertEqual(values[4], entry.stop_desc)
        self.assertEqual(WHEELCHAIR_TO_INT[WheelchairBoarding.yes],
                         int(entry.wheelchair_boarding))

        values = ["stop_id_1", "stop 1", "", "", "", ""]
        entry = GTFSStopEntry.from_series(pd.Series(values, index=index))
        self.assertEqual(values[0], entry.stop_id)
        self.assertEqual(values[1], entry.stop_name)
        self.assertEqual(None, entry.stop_lat)
        self.assertEqual(None, entry.stop_lon)
        self.assertEqual(values[4], entry.stop_desc)
        self.assertEqual(0, WHEELCHAIR_TO_INT[entry.wheelchair_boarding])


class TestGTFSStops(GTFSOutputBaseClass):
    def test_add(self) -> None:
        stops = GTFSStops(self.temp_path)
        self.assertEqual(0, len(stops.entries))
        stops.add("test stop")
        self.assertEqual(1, len(stops.entries))
        stops.add("test stop")
        self.assertEqual(1, len(stops.entries))
        stops.add("test stop 2")
        self.assertEqual(2, len(stops.entries))
        self.assertEqual("test stop", stops.entries[0].stop_name)
        self.assertEqual("test stop 2", stops.entries[1].stop_name)

    def test_get(self) -> None:
        stops = GTFSStops(self.temp_path)
        stops.add("test stop A")
        stop1 = stops.entries[0]
        self.assertEqual(stop1, stops.get("test stop A"))
        stops.add("test stop B")
        stop2 = stops.entries[1]
        self.assertEqual(stop1, stops.get("test stop A"))
        self.assertEqual(stop2, stops.get("test stop B"))

    def test_get_by_stop_id(self) -> None:
        stops = GTFSStops(self.temp_path)
        stops.add("test")
        stops.add("test2")
        stop1 = stops.entries[0]
        stop2 = stops.entries[1]
        self.assertEqual(stop1, stops.get_by_stop_id(stop1.stop_id))
        self.assertEqual(stop2, stops.get_by_stop_id(stop2.stop_id))
        with self.assertRaises(KeyError):
            stops.get_by_stop_id("test stop B")

    def test_get_existing_stops(self) -> None:
        stops = GTFSStops(self.temp_path)
        names = ["stop_a", "stop_b", "stop_d"]
        locs = {"stop_a": (48.2, 32.2, False),
                "stop_b": (32.1, 39.9, False),
                "stop_d": (None, None, False)}
        result = {}
        for name in names:
            stops.add(name)
            stop = stops.get(name)
            stop.set_location(*locs[name])
            result[stop.stop_id] = stop.stop_lat, stop.stop_lon
        stops.add("stop_c")
        stops.add("stop_e")
        existing_locs = stops.get_existing_stops(list(result.keys()))
        self.assertDictEqual(result, existing_locs)
