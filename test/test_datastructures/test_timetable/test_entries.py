from pdf2gtfs.datastructures.timetable.entries import (
    TimeTableEntry, TimeTableRepeatEntry)
from pdf2gtfs.datastructures.timetable.stops import Stop
from test import P2GTestCase


class TestTimeTableEntry(P2GTestCase):
    def test_set_value(self) -> None:
        stop_1 = Stop("stop_1", 1)
        stop_2 = Stop("stop_2", 2)
        entry = TimeTableEntry("test")
        self.assertEqual({}, entry.values)
        entry.set_value(stop_1, "03.33")
        self.assertEqual("03.33", entry.get_value(stop_1))
        self.assertEqual(1, len(entry.values))
        entry.set_value(stop_1, "06.66")
        self.assertEqual("06.66", entry.get_value(stop_1))
        self.assertEqual(1, len(entry.values))
        entry.set_value(stop_2, "03.33")
        self.assertEqual("03.33", entry.get_value(stop_2))
        self.assertEqual(2, len(entry.values))

    def test_get_value(self) -> None:
        stop_1 = Stop("stop_1", 1)
        stop_2 = Stop("stop_2", 2)
        entry = TimeTableEntry("test")
        self.assertEqual(0, len(entry.values))
        self.assertIsNone(entry.get_value(stop_1))
        self.assertIsNone(entry.get_value(stop_2))
        entry.set_value(stop_2, "stop 2")
        self.assertIsNone(entry.get_value(stop_1))
        self.assertEqual("stop 2", entry.get_value(stop_2))
        entry.set_value(stop_1, "stop 1")
        self.assertEqual("stop 1", entry.get_value(stop_1))
        self.assertEqual("stop 2", entry.get_value(stop_2))


class TestTimeTableRepeatEntry(P2GTestCase):
    @classmethod
    def setUpClass(cls: P2GTestCase, **kwargs) -> None:
        super().setUpClass(False, True)

    def test_interval_str_to_int_list(self) -> None:
        int_list = TimeTableRepeatEntry.interval_str_to_int_list("1")
        self.assertEqual([1], int_list)
        int_list = TimeTableRepeatEntry.interval_str_to_int_list("1, 2, 3")
        self.assertEqual([1, 2, 3], int_list)
        int_list = TimeTableRepeatEntry.interval_str_to_int_list("1-3")
        self.assertEqual([1, 2, 3], int_list)
        # Either - or ,
        int_list = TimeTableRepeatEntry.interval_str_to_int_list("1-3, 5-7")
        self.assertEqual([], int_list)
        int_list = TimeTableRepeatEntry.interval_str_to_int_list("1-3a")
        self.assertEqual([], int_list)
