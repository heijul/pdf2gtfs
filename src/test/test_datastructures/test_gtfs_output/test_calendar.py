import datetime as dt
from dataclasses import fields
from pathlib import Path

import pandas as pd

from datastructures.gtfs_output.calendar import (
    DayIsActive, GTFSCalendar, GTFSCalendarEntry, ServiceDay, WEEKDAY_NAMES)
from test_datastructures.test_gtfs_output import GTFSOutputBaseClass
from test import P2GTestCase


class TestServiceDay(P2GTestCase):
    def setUp(self) -> None:
        self.date1 = ServiceDay(dt.date(2022, 1, 4))
        self.date2 = ServiceDay(dt.date(2022, 1, 4))
        self.date3 = ServiceDay(dt.date(2022, 1, 14))
        self.date4 = ServiceDay(dt.date(2022, 11, 4))
        self.date5 = ServiceDay(dt.date(2023, 1, 4))

    def test_to_output(self) -> None:
        self.assertEqual("\"20220104\"", self.date1.to_output())
        self.assertEqual("\"20220104\"", self.date2.to_output())
        self.assertEqual("\"20220114\"", self.date3.to_output())
        self.assertEqual("\"20221104\"", self.date4.to_output())
        self.assertEqual("\"20230104\"", self.date5.to_output())

    def test___comparisons__(self) -> None:
        self.assertEqual(self.date1, self.date2)
        self.assertNotEqual(self.date1, self.date3)
        self.assertNotEqual(self.date1, self.date4)
        self.assertNotEqual(self.date1, self.date5)


class TestGTFSCalendarEntry(GTFSOutputBaseClass):
    def setUp(self) -> None:
        days = ["0", "1", "2", "3", "4"]
        self.weekdays_1 = GTFSCalendarEntry(days)
        self.weekdays_2 = GTFSCalendarEntry(days, {"test_annotation"})
        self.weekdays_h = GTFSCalendarEntry(days + ["h"])
        self.weekends_h = GTFSCalendarEntry(["5", "6", "h"])

    def test__set_days(self) -> None:
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

    def test__set_annotations(self) -> None:
        entry = GTFSCalendarEntry()
        self.assertEqual(entry.annotations, set())
        annots = {"test_annotation"}
        entry._set_annotations(annots)
        self.assertEqual(entry.annotations, annots)

    def test_same_days(self) -> None:
        self.assertTrue(self.weekdays_1.same_days(self.weekdays_1))
        self.assertTrue(self.weekdays_1.same_days(self.weekdays_2))
        self.assertTrue(self.weekdays_2.same_days(self.weekdays_1))
        self.assertFalse(self.weekdays_2.same_days(self.weekends_h))
        self.assertFalse(self.weekdays_2.same_days(self.weekdays_h))
        self.assertFalse(self.weekends_h.same_days(self.weekdays_h))

    def test_disable(self) -> None:
        entries = [self.weekdays_1, self.weekdays_2,
                   self.weekdays_h, self.weekends_h]
        for i, entry in enumerate(entries):
            with self.subTest(i=i):
                self.assertTrue(any([getattr(entry, day).active
                                     for day in WEEKDAY_NAMES]))
                entry.disable()
                self.assertFalse(any([getattr(entry, day).active
                                      for day in WEEKDAY_NAMES]))

    def test_eq(self) -> None:
        self.assertEqual(self.weekdays_1, self.weekdays_1)
        self.assertNotEqual(self.weekdays_1, self.weekdays_2)
        self.assertNotEqual(self.weekdays_1, self.weekdays_h)
        self.assertNotEqual(self.weekdays_2, self.weekends_h)

    def test_from_series(self) -> None:
        index = [field.name for field in fields(GTFSCalendarEntry)]
        values = ["service_id01", "1", "0", "1", "0", "1", "0", "1",
                  "20220410", "20221004"]
        series = pd.Series(values, index=index)
        entry = GTFSCalendarEntry.from_series(series)
        self.assertEqual(values[0], entry.service_id)
        self.assertTrue(entry.monday.active)
        self.assertFalse(entry.tuesday.active)
        self.assertTrue(entry.wednesday.active)
        self.assertFalse(entry.thursday.active)
        self.assertTrue(entry.friday.active)
        self.assertFalse(entry.saturday.active)
        self.assertTrue(entry.sunday.active)
        start_date = dt.date(2022, 4, 10)
        end_date = dt.date(2022, 10, 4)
        self.assertEqual(start_date, entry.start_date.date)
        self.assertEqual(end_date, entry.end_date.date)


class TestCalendar(GTFSOutputBaseClass):
    @classmethod
    def setUpClass(cls, name="calendar.txt", **kwargs) -> None:
        super().setUpClass(name)

    def test_add(self) -> None:
        days = ["0", "1", "2"]
        annots = set()
        temp_dir_path = Path(self.temp_dir.name)
        c = GTFSCalendar(temp_dir_path)
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
        temp_dir_path = Path(self.temp_dir.name)
        c = GTFSCalendar(temp_dir_path)
        days = ["0", "5", "3"]
        e = GTFSCalendarEntry(days, None)
        c.add(days, set())
        self.assertEqual(e, c.get(e))
        self.assertEqual(e, c.entries[0])
        self.assertNotEqual(id(e), id(c.get(e)))

    def test_group_by_holiday(self) -> None:
        temp_dir_path = Path(self.temp_dir.name)
        c = GTFSCalendar(temp_dir_path)
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

    def create_calendar(self) -> GTFSCalendar:
        c = GTFSCalendar(self.temp_path)
        c.add(["0", "1", "2"], set())
        c.add(["2", "1", "0"], {"test"})
        c.add(["4", "3", "2"], {"test2"})
        c.add(["5", "6", "h"], {"test"})
        c.add(["5", "6"], {"test", "test2"})
        return c

    def test__group_by(self) -> None:
        def grouper(e: GTFSCalendarEntry) -> bool:
            return e.monday.active

        c = self.create_calendar()
        monday_active, monday_inactive = c._group_by(grouper)
        for i, entry in enumerate(monday_active):
            self.assertTrue(entry.monday.active)
        for i, entry in enumerate(monday_inactive):
            self.assertFalse(entry.monday.active)

    def test_get_with_annot(self) -> None:
        c = self.create_calendar()
        entries = c.get_with_annot("test")
        self.assertEqual(3, len(entries))
        self.assertTrue(all(["test" in e.annotations for e in entries]))
        entries = c.get_with_annot("test2")
        self.assertEqual(2, len(entries))
        self.assertTrue(all(["test2" in e.annotations for e in entries]))
        entries = c.get_with_annot("te")
        self.assertEqual(0, len(entries))

    def test_get_annotations(self) -> None:
        self.assertEqual([], GTFSCalendar(self.temp_path).get_annotations())
        c = self.create_calendar()
        self.assertEqual(["test", "test2"], c.get_annotations())
        c.add(["h"], {"teeest"})
        self.assertEqual(sorted(["test", "test2", "teeest"]),
                         c.get_annotations())
