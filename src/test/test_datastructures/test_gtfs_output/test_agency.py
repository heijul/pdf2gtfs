from dataclasses import fields
from pathlib import Path

import pandas as pd

from config import Config
from datastructures.gtfs_output.agency import (
    GTFSAgency, DummyGTFSAgencyEntry,
    GTFSAgencyEntry)
from test_datastructures.test_gtfs_output import GTFSOutputBaseClass


class TestGTFSAgencyEntry(GTFSOutputBaseClass):
    def test_from_series(self) -> None:
        index = [field.name for field in fields(GTFSAgencyEntry)]
        series = pd.Series(
            ["a01", "transit_agency", "www.example.com", "Europe/Berlin"],
            index=index)
        entry = GTFSAgencyEntry.from_series(series)
        self.assertEqual("a01", entry.agency_id)
        self.assertEqual("transit_agency", entry.agency_name)
        self.assertEqual("www.example.com", entry.agency_url)
        self.assertEqual("Europe/Berlin", entry.agency_timezone)

    def test_values(self) -> None:
        entry = GTFSAgencyEntry(
            "agency01", "www.example.com", "Europe/Berlin", "a02")
        values = ["a02", "agency01", "www.example.com", "Europe/Berlin"]
        self.assertEqual(values, entry.values)


class TestAgency(GTFSOutputBaseClass):
    @classmethod
    def setUpClass(cls, name="agency.txt", **kwargs) -> None:
        super().setUpClass(name)

    def _create_agency(self, entry_count: int = 1):
        lines = ["agency_id,agency_name,agency_url,agency_timezone"]
        lines += [f"{i},agency_{i},https://www.pdf2gtfs.com/{i},Europe/Berlin"
                  for i in range(entry_count)]
        lines = "\n".join(lines)
        with open(self.filename, "w") as fil:
            fil.write(lines)

    def test_create_dummy_agency(self) -> None:
        temp_dir_path = Path(self.temp_dir.name)
        agency = GTFSAgency(temp_dir_path)
        self.assertEqual(1, len(agency.entries))
        self.assertTrue(isinstance(agency.entries[0], DummyGTFSAgencyEntry))

    def test_read_input_files(self) -> None:
        self._create_agency(1)
        Config.input_files = [self.filename]
        agency = GTFSAgency(self.filename.parent)
        self.assertEqual(1, len(agency.entries))
        entry = agency.entries[0]
        self.assertFalse(isinstance(entry, DummyGTFSAgencyEntry))
        self.assertEqual(entry.agency_id, "0")
        self.assertEqual(entry.agency_name, "agency_0")
        self.assertEqual(entry.agency_url, "https://www.pdf2gtfs.com/0")
        self.assertEqual(entry.agency_timezone, "Europe/Berlin")
