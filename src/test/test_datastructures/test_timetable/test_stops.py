from unittest import TestCase

from datastructures.timetable.stops import Stop, StopList
from test import P2GTestCase


class TestStop(P2GTestCase):
    def test__clean(self) -> None:
        s1 = Stop(" test a.-,# ", 1)
        self.assertEqual(" test a.-,# ", s1.name)
        s1.clean()
        self.assertEqual("test a.-,#", s1.name)

    def test___eq(self) -> None:
        s1 = Stop("Frankfurt Hauptbahnhof", 1)
        s2 = Stop("Frankfurt Hauptbahnhof", 0)
        self.assertEqual(s1, s2)
        s1.annotation = "an"
        self.assertNotEqual(s1, s2)
        s2.annotation = "an"
        self.assertEqual(s1, s2)


class TestStopList(P2GTestCase):
    def test_stops(self) -> None:
        stop_list = StopList()
        stops = []
        for i in range(10):
            stop = Stop(f"stop {i}", i)
            stop_list.add_stop(stop)
            stops.append(stop)
        self.assertEqual(10, len(stop_list.stops))
        for i in range(3, 7):
            stops[i].is_connection = True
        self.assertEqual(6, len(stop_list.stops))
        self.assertListEqual(stops[:3] + stops[7:], stop_list.stops)

    def test_add_stop(self) -> None:
        stop_list = StopList()
        for i in range(10):
            with self.subTest(i=i):
                stop = Stop(f"stop {i}", i)
                stop_list.add_stop(stop)
                self.assertEqual(stop, stop_list.all_stops[-1])

    def test_get_from_id(self) -> None:
        stop_list = StopList()
        stops = []
        for i in range(10):
            stop = Stop(f"stop {i}", i + 42)
            stop_list.add_stop(stop)
            stops.append(stop)
        for i in range(10):
            with self.subTest(i=i):
                self.assertEqual(stops[i], stop_list.get_from_id(i + 42))

    def test_add_annotation(self) -> None:
        stop_list = StopList()
        stops = []
        for i in range(10):
            stop = Stop(f"stop {i}", i)
            stop_list.add_stop(stop)
            stops.append(stop)

    def test_clean(self) -> None:
        stop_list = StopList()
        stops = []
        for i in range(10):
            stop = Stop(f" stop {i} ", i)
            stop_list.add_stop(stop)
            stops.append(stop)
        for i in range(10):
            with self.subTest(i=i):
                self.assertTrue(stops[i].name.startswith(" "))
                self.assertTrue(stops[i].name.endswith(" "))
        stop_list.clean()
        for i in range(10):
            with self.subTest(i=i):
                name = stops[i].name
                stops[i].clean()
                self.assertEqual(name, stops[i].name)
