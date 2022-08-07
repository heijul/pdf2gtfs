from unittest import TestCase

from datastructures.gtfs_output.calendar import (
    CalendarEntry, WEEKDAY_NAMES, DayIsActive, Calendar)
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

    def test_try_add(self):
        days = ["0", "1", "2"]
        annots = set()
        c = Calendar()
        self.assertEqual(0, len(c.entries))
        c.try_add(days, annots)
        self.assertEqual(1, len(c.entries))
        c.try_add(days, annots)
        self.assertEqual(1, len(c.entries))
        c.try_add(days, {"test_annotation"})
        self.assertEqual(2, len(c.entries))
        c.try_add(days + ["h"], {"test_annotation"})
        self.assertEqual(3, len(c.entries))

    def test_get(self):
        c = Calendar()
        days = ["0", "5", "3"]
        e = CalendarEntry(days, None)
        c.try_add(days, set())
        self.assertEqual(e, c.get(e))
        self.assertEqual(e, c.entries[0])
        self.assertNotEqual(id(e), id(c.get(e)))

    def test_group_by_holiday(self):
        c = Calendar()
        for i in range(7):
            if i % 2:
                c.try_add(["h"], {"holiday", str(i)})
            else:
                c.try_add(["1", "2"], {str(i)})
        on_holidays, no_holidays = c.group_by_holiday()
        self.assertEqual(len(c.entries), len(on_holidays) + len(no_holidays))
        self.assertEqual(3, len(on_holidays))
        self.assertEqual(4, len(no_holidays))
        for entry in on_holidays:
            self.assertTrue(entry.on_holidays)
        for entry in no_holidays:
            self.assertFalse(entry.on_holidays)