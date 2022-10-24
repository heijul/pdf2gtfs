from unittest import TestCase

from datastructures.gtfs_output.calendar import (
    GTFSCalendar, GTFSCalendarEntry, DayIsActive, WEEKDAY_NAMES)
from test_gtfs_output import GTFSOutputBaseClass


class TestCalendarEntry(TestCase):
    def setUp(self) -> None:
        days = ["0", "1", "2", "3", "4"]
        self.weekdays_1 = GTFSCalendarEntry(days)
        self.weekdays_2 = GTFSCalendarEntry(days, {"test_annotation"})
        self.weekdays_h = GTFSCalendarEntry(days + ["h"])
        self.weekends_h = GTFSCalendarEntry(["5", "6", "h"])

    def test_set_annotations(self) -> None:
        entry = GTFSCalendarEntry()
        self.assertEqual(entry.annotations, set())
        annots = {"test_annotation"}
        entry._set_annotations(annots)
        self.assertEqual(entry.annotations, annots)

    def test_set_days(self) -> None:
        entry = GTFSCalendarEntry()
        days = ["0", "1", "2", "3", "4", "5", "6", "h"]
        entry._set_days(days)
        for weekday in WEEKDAY_NAMES:
            self.assertTrue(getattr(entry, weekday), DayIsActive(True))
        self.assertTrue(entry.on_holidays)
        entry = GTFSCalendarEntry()
        days = ["3", "1", "2"]
        entry._set_days(days)
        for weekday in WEEKDAY_NAMES:
            is_active = DayIsActive(str(weekday) in days)
            self.assertTrue(getattr(entry, weekday), is_active)
            self.assertFalse(entry.on_holidays)

    def test_same_days(self) -> None:
        self.assertTrue(self.weekdays_1.same_days(self.weekdays_1))
        self.assertTrue(self.weekdays_1.same_days(self.weekdays_2))
        self.assertTrue(self.weekdays_2.same_days(self.weekdays_1))
        self.assertFalse(self.weekdays_2.same_days(self.weekends_h))
        self.assertFalse(self.weekdays_2.same_days(self.weekdays_h))
        self.assertFalse(self.weekends_h.same_days(self.weekdays_h))

    def test_eq(self) -> None:
        self.assertEqual(self.weekdays_1, self.weekdays_1)
        self.assertNotEqual(self.weekdays_1, self.weekdays_2)
        self.assertNotEqual(self.weekdays_1, self.weekdays_h)
        self.assertNotEqual(self.weekdays_2, self.weekends_h)


class TestCalendar(GTFSOutputBaseClass):
    @classmethod
    def setUpClass(cls, name="calendar.txt") -> None:
        super().setUpClass(name)

    def test_try_add(self) -> None:
        days = ["0", "1", "2"]
        annots = set()
        c = GTFSCalendar()
        self.assertEqual(0, len(c.entries))
        c.add(days, annots)
        self.assertEqual(1, len(c.entries))
        c.add(days, annots)
        self.assertEqual(1, len(c.entries))
        c.add(days, {"test_annotation"})
        self.assertEqual(2, len(c.entries))
        c.add(days + ["h"], {"test_annotation"})
        self.assertEqual(3, len(c.entries))

    def test_get(self) -> None:
        c = GTFSCalendar()
        days = ["0", "5", "3"]
        e = GTFSCalendarEntry(days, None)
        c.add(days, set())
        self.assertEqual(e, c.get(e))
        self.assertEqual(e, c.entries[0])
        self.assertNotEqual(id(e), id(c.get(e)))

    def test_group_by_holiday(self) -> None:
        c = GTFSCalendar()
        for i in range(7):
            if i % 2:
                c.add(["h"], {"holiday", str(i)})
            else:
                c.add(["1", "2"], {str(i)})
        on_holidays, no_holidays = c.group_by_holiday()
        self.assertEqual(len(c.entries), len(on_holidays) + len(no_holidays))
        self.assertEqual(3, len(on_holidays))
        self.assertEqual(4, len(no_holidays))
        for entry in on_holidays:
            self.assertTrue(entry.on_holidays)
        for entry in no_holidays:
            self.assertFalse(entry.on_holidays)
