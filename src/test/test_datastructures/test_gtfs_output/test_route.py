from pathlib import Path

from config import Config
from datastructures.gtfs_output.routes import (
    get_route_type, get_route_type_gtfs_value, GTFSRouteEntry, GTFSRoutes,
    RouteType)
from datastructures.timetable.entries import TimeTableEntry
from test_datastructures.test_timetable import create_stops
from test import P2GTestCase


class TestRouteType(P2GTestCase):
    def test_to_output(self) -> None:
        routetype = RouteType.Tram
        self.assertEqual(routetype.to_output(), "0")
        routetype = RouteType.AerialLift
        self.assertEqual(routetype.to_output(), "6")
        # RouteType ID and GTFS ID are different.
        routetype = RouteType(6)
        self.assertEqual(routetype.to_output(), "3")


class TestRoute(P2GTestCase):
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


class TestRoutes(P2GTestCase):
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

    def test_add(self) -> None:
        dummy_dir = Path("")
        routes = GTFSRoutes(dummy_dir, "agency_0")
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
