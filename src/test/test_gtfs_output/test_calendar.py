from unittest import TestCase

from datastructures.gtfs_output.calendar import (
    CalendarEntry, WEEKDAY_NAMES, DayIsActive)
from test_gtfs_output import GTFSOutputBaseClass


class TestCalendarEntry(TestCase):
    def setUp(self) -> None:
        days = ["0", "1", "2", "3", "4"]
        self.weekdays_1 = CalendarEntry(days)
        self.weekdays_2 = CalendarEntry(days, {"test_annotation"})
        self.weekdays_h = CalendarEntry(days + ["h"])
        self.weekends_h = CalendarEntry(["5", "6", "h"])

    def test_set_annotations(self):
        entry = CalendarEntry()
        self.assertEqual(entry.annotations, set())
        annots = {"test_annotation"}
        entry._set_annotations(annots)
        self.assertEqual(entry.annotations, annots)

    def test_set_days(self):
        entry = CalendarEntry()
        days = ["0", "1", "2", "3", "4", "5", "6", "h"]
        entry._set_days(days)
        for weekday in WEEKDAY_NAMES:
            self.assertTrue(getattr(entry, weekday), DayIsActive(True))
        self.assertTrue(entry.on_holidays)
        entry = CalendarEntry()
        days = ["3", "1", "2"]
        entry._set_days(days)
        for weekday in WEEKDAY_NAMES:
            is_active = DayIsActive(str(weekday) in days)
            self.assertTrue(getattr(entry, weekday), is_active)
            self.assertFalse(entry.on_holidays)

    def test_same_days(self):
        self.assertTrue(self.weekdays_1.same_days(self.weekdays_1))
        self.assertTrue(self.weekdays_1.same_days(self.weekdays_2))
        self.assertTrue(self.weekdays_2.same_days(self.weekdays_1))
        self.assertFalse(self.weekdays_2.same_days(self.weekends_h))
        self.assertFalse(self.weekdays_2.same_days(self.weekdays_h))
        self.assertFalse(self.weekends_h.same_days(self.weekdays_h))

    def test_eq(self):
        self.assertEqual(self.weekdays_1, self.weekdays_1)
        self.assertNotEqual(self.weekdays_1, self.weekdays_2)
        self.assertNotEqual(self.weekdays_1, self.weekdays_h)
        self.assertNotEqual(self.weekdays_2, self.weekends_h)


class TestCalendar(GTFSOutputBaseClass):
    @classmethod
    def setUpClass(cls, name="calendar.txt") -> None:
        super().setUpClass(name)
