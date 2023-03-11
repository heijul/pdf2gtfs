from dataclasses import fields

import pandas as pd

from pdf2gtfs.config import Config
from pdf2gtfs.datastructures.gtfs_output.routes import (
    get_route_type, get_route_type_gtfs_value, GTFSRouteEntry, GTFSRoutes,
    RouteType)
from pdf2gtfs.datastructures.timetable.entries import TimeTableEntry
from test import P2GTestCase
from test.test_datastructures.test_gtfs_output import GTFSOutputBaseClass
from test.test_datastructures.test_timetable import create_stops


class TestRouteType(P2GTestCase):
    def test_to_output(self) -> None:
        routetype = RouteType.Tram
        self.assertEqual(routetype.to_output(), "0")
        routetype = RouteType.AerialLift
        self.assertEqual(routetype.to_output(), "6")
        # RouteType ID and GTFS ID are different.
        routetype = RouteType(6)
        self.assertEqual(routetype.to_output(), "3")


class TestGTFSRouteEntry(P2GTestCase):
    def test_eq(self) -> None:
        r1 = GTFSRouteEntry("1", "short_name", "long_name")
        r2 = GTFSRouteEntry("1", "short_name", "long_name")
        r3 = GTFSRouteEntry("1", "short_name2", "long_name")
        r4 = GTFSRouteEntry("1", "short_name2", "long_name3")
        r5 = GTFSRouteEntry("44", "short_name2", "long_name3")
        self.assertEqual(r1, r1)
        self.assertEqual(r1, r2)
        self.assertNotEqual(r1, r3)
        self.assertNotEqual(r1, r4)
        self.assertEqual(r2, r2)
        self.assertNotEqual(r2, r3)
        self.assertNotEqual(r2, r4)
        self.assertEqual(r3, r3)
        self.assertNotEqual(r3, r4)
        self.assertNotEqual(r3, r4)
        self.assertEqual(r4, r4)
        self.assertNotEqual(r1, r5)
        self.assertNotEqual(r2, r5)
        self.assertNotEqual(r3, r5)
        self.assertNotEqual(r4, r5)

    def test_route_type(self) -> None:
        route = GTFSRouteEntry("1", "short", "long")
        route_type = get_route_type(Config.gtfs_routetype)
        self.assertEqual(
            get_route_type_gtfs_value(route_type), route.route_type)

    def test_get_field_value(self) -> None:
        entry = GTFSRouteEntry("a1", "s_name", "l_name", "r1", RouteType(3))
        entry_fields = fields(entry)
        self.assertEqual("r1", entry.get_field_value(entry_fields[0]))
        self.assertEqual("a1", entry.get_field_value(entry_fields[1]))
        self.assertEqual("s_name", entry.get_field_value(entry_fields[2]))
        self.assertEqual("l_name", entry.get_field_value(entry_fields[3]))
        self.assertEqual(3, entry.get_field_value(entry_fields[4]))

    def test_from_series(self) -> None:
        index = [f.name for f in fields(GTFSRouteEntry)]
        values = ["route_id3", "agency_id1", "short_name", "long_name", "3"]
        s = pd.Series(values, index=index)
        entry = GTFSRouteEntry.from_series(s)
        self.assertEqual(values[0], entry.route_id)
        self.assertEqual(values[1], entry.agency_id)
        self.assertEqual(values[2], entry.route_short_name)
        self.assertEqual(values[3], entry.route_long_name)
        self.assertEqual("Bus", entry.route_type.name)
        # Test some empty values
        index = [f.name for f in fields(GTFSRouteEntry)]
        values = ["route_id3", "agency_id1", "short_name", "", "3"]
        s = pd.Series(values, index=index)
        entry = GTFSRouteEntry.from_series(s)
        self.assertEqual(values[3], entry.route_long_name)
        # Test some empty values
        index = [f.name for f in fields(GTFSRouteEntry)]
        values = ["route_id3", "agency_id1", "", "long_name", "3"]
        s = pd.Series(values, index=index)
        entry = GTFSRouteEntry.from_series(s)
        self.assertEqual(values[2], entry.route_short_name)


class TestGTFSRoutes(GTFSOutputBaseClass):
    def test_add(self) -> None:
        routes = GTFSRoutes(self.temp_path, "agency_0")
        self.assertEqual(0, len(routes.entries))
        route1 = routes.add("short1", "long1")
        self.assertEqual(1, len(routes.entries))
        route2 = routes.add("short1", "long2")
        self.assertEqual(2, len(routes.entries))
        route3 = routes.add("short1", "long2")
        self.assertEqual(2, len(routes.entries))
        self.assertNotEqual(id(route1), id(route2))
        self.assertEqual(route2, route3)
        self.assertEqual(id(route2), id(route3))

    def test_get(self) -> None:
        r = GTFSRoutes(self.temp_path, "agency_0")
        e1 = r.add("short1", "long1")
        e2 = r.add("short2", "long2")
        e3 = r.add("short3", "long3")
        e4 = r.add("short1", "long2")
        e5 = r.add("short3", "long2")
        self.assertEqual(e1, r.get(e1.route_short_name, e1.route_long_name))
        self.assertEqual(e2, r.get(e2.route_short_name, e2.route_long_name))
        self.assertEqual(e3, r.get(e3.route_short_name, e3.route_long_name))
        self.assertEqual(e4, r.get(e4.route_short_name, e4.route_long_name))
        self.assertEqual(e5, r.get(e5.route_short_name, e5.route_long_name))

    def test_names_from_entry(self) -> None:
        stops = create_stops(3)
        e = TimeTableEntry("montag-freitag")
        e.set_value(stops[0], "6.00")
        e.set_value(stops[1], "6.30")
        e.set_value(stops[2], "7.42")
        short_name, long_name = GTFSRoutes.names_from_entry(e)
        self.assertEqual(short_name, "")
        self.assertEqual(long_name, "stop0-stop2")
        e.route_name = "testroute"
        short_name, _ = GTFSRoutes.names_from_entry(e)
        self.assertEqual(short_name, "testroute")

    def test_add_from_entry(self) -> None:
        r = GTFSRoutes(self.temp_path, "agency")
        Config.header_values = {"montag-freitag": "1, 2, 3, 4"}
        stops = create_stops(3)
        tt_entry = TimeTableEntry("Montag-Freitag")
        tt_entry.set_value(stops[0], "6.00")
        tt_entry.set_value(stops[1], "6.30")
        tt_entry.set_value(stops[2], "7.42")
        self.assertEqual(0, len(r.entries))
        r.add_from_entry(tt_entry)
        e1 = r.get_from_entry(tt_entry)
        self.assertEqual(r.agency_id, e1.agency_id)
        self.assertEqual(tt_entry.route_name, e1.route_short_name)
        long_name = f"{stops[0].name}-{stops[-1].name}"
        self.assertEqual(long_name, e1.route_long_name)

    def test_get_from_entry(self) -> None:
        r = GTFSRoutes(self.temp_path, "aa1")
        stops = create_stops(3)
        tt_entry = TimeTableEntry("Montag-Freitag")
        tt_entry.set_value(stops[0], "6.00")
        tt_entry.set_value(stops[1], "6.30")
        tt_entry.set_value(stops[2], "7.42")
        short_name = tt_entry.route_name
        long_name = f"{stops[0].name}-{stops[-1].name}"
        r.add_from_entry(tt_entry)
        e = r.get_from_entry(tt_entry)
        self.assertEqual(short_name, e.route_short_name)
        self.assertEqual(long_name, e.route_long_name)


class Test(P2GTestCase):
    def test_get_route_type(self) -> None:
        str_rts = ["traM", "Bus", "metro", "RAIL", "", "tr am"]
        results = [RouteType.Tram, RouteType.Bus, RouteType.Metro,
                   RouteType.Rail, None, None]
        for i, (rt, result) in enumerate(zip(str_rts, results, strict=True)):
            with self.subTest(i=i):
                self.assertEqual(result, get_route_type(rt))
        int_rts = ["0", "1 ", "2", "8", "4"]
        results = [RouteType.Tram, RouteType.Subway, RouteType.Rail,
                   None, RouteType.Ferry]
        for j, (rt, result) in enumerate(zip(int_rts, results, strict=True)):
            with self.subTest(j=j):
                self.assertEqual(result, get_route_type(rt))

    def test_get_route_type_gtfs_value(self) -> None:
        rt = RouteType.LightRail
        gtfs_value = get_route_type_gtfs_value(rt)
        self.assertEqual(0, gtfs_value)
        self.assertEqual(RouteType.Tram, RouteType(gtfs_value))
