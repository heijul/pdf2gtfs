import datetime as dt
from dataclasses import fields

import pandas as pd

from pdf2gtfs.datastructures.gtfs_output.calendar_dates import (
    GTFSCalendarDateEntry, GTFSCalendarDates)
from test.test_datastructures.test_gtfs_output import GTFSOutputBaseClass


class TestGTFSCalendarDateEntry(GTFSOutputBaseClass):
    def test_from_series(self) -> None:
        index = [f.name for f in fields(GTFSCalendarDateEntry)]
        values = ["service_id666", "20220410", "1"]
        series = pd.Series(values, index)
        entry = GTFSCalendarDateEntry.from_series(series)
        self.assertEqual(values[0], entry.service_id)
        self.assertEqual(values[1], entry.date)
        self.assertEqual(1, entry.exception_type)


class TestGTFSCalendarDates(GTFSOutputBaseClass):
    def test_add(self) -> None:
        cd = GTFSCalendarDates(self.temp_path)
        self.assertEqual(0, len(cd.entries))
        e1 = cd.add("s01", dt.date(2022, 1, 1), True)
        self.assertEqual(1, len(cd.entries))
        cd.add("s02", dt.date(2022, 1, 1), True)
        self.assertEqual(2, len(cd.entries))
        e2 = cd.add("s01", dt.date(2022, 1, 1), True)
        self.assertEqual(e1, e2)
        self.assertEqual(2, len(cd.entries))
        cd.add("s01", dt.date(2022, 5, 12), False)
        self.assertEqual(3, len(cd.entries))
        e3 = cd.add("s01", dt.date(2022, 1, 1), False)
        self.assertEqual(4, len(cd.entries))
        self.assertNotEqual(e1, e3)

    def test_add_multiple(self) -> None:
        dates = [dt.date(2022, 2, 3), dt.date(2033, 3, 31),
                 dt.date(2022, 1, 1), dt.date(2033, 1, 1)]
        cd = GTFSCalendarDates(self.temp_path)
        cd.add("s01", dates[0], True)
        cd.add_multiple("s01", dates, True)
        self.assertEqual(4, len(cd.entries))
