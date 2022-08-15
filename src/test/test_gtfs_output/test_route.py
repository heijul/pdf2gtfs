from unittest import TestCase

from config import Config
from datastructures.gtfs_output.route import Route, Routes, RouteType
from datastructures.timetable.entries import TimeTableEntry
from test_timetable import create_stops


class TestRouteType(TestCase):
    def test_to_output(self) -> None:
        routetype = RouteType.Tram
        self.assertEqual(routetype.to_output(), "0")
        routetype = RouteType.AerialLift
        self.assertEqual(routetype.to_output(), "6")
        routetype = RouteType(6)
        self.assertEqual(routetype.to_output(), "6")


class TestRoute(TestCase):
    def test_eq(self) -> None:
        # TODO: Test with different agency ids
        r1 = Route(1, "short_name", "long_name")
        r2 = Route(1, "short_name", "long_name")
        r3 = Route(1, "short_name2", "long_name")
        r4 = Route(1, "short_name2", "long_name3")
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

    def test_route_type(self) -> None:
        route = Route(1, "short", "long")
        routetype = RouteType[Config.gtfs_routetype]
        self.assertEqual(routetype, route.route_type)


class TestRoutes(TestCase):
    def test_names_from_entry(self) -> None:
        stops = create_stops(3)
        e = TimeTableEntry("montag-freitag")
        e.set_value(stops[0], "6.00")
        e.set_value(stops[1], "6.30")
        e.set_value(stops[2], "7.42")
        short_name, long_name = Routes.names_from_entry(e)
        self.assertEqual(short_name, "")
        self.assertEqual(long_name, "stop0-stop2")
        e.route_name = "testroute"
        short_name, _ = Routes.names_from_entry(e)
        self.assertEqual(short_name, "testroute")

    def test_add(self) -> None:
        routes = Routes()
        self.assertEqual(0, len(routes.entries))
        route1 = routes.add(short_name="short1", long_name="long1")
        self.assertEqual(1, len(routes.entries))
        route2 = routes.add(short_name="short1", long_name="long2")
        self.assertEqual(2, len(routes.entries))
        route3 = routes.add(short_name="short1", long_name="long2")
        self.assertEqual(2, len(routes.entries))
        self.assertNotEqual(id(route1), id(route2))
        self.assertEqual(route2, route3)
        self.assertEqual(id(route2), id(route3))
