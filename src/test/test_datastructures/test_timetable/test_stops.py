from datastructures.timetable.stops import Stop
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
