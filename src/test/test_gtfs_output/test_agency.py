import os

from config import Config
from datastructures.gtfs_output.agency import GTFSAgency, DummyGTFSAgencyEntry
from test_gtfs_output import GTFSOutputBaseClass


class TestAgency(GTFSOutputBaseClass):
    @classmethod
    def setUpClass(cls, name="agency.txt") -> None:
        super().setUpClass(name)

    def setUp(self) -> None:
        Config.output_dir = self.temp_dir.name

    def tearDown(self) -> None:
        try:
            os.unlink(self.filename)
        except OSError:
            pass

    def _create_agency(self, entry_count: int = 1):
        lines = ["agency_id,agency_name,agency_url,agency_timezone"]
        lines += [f"{i},agency_{i},https://www.pdf2gtfs.com/{i},Europe/Berlin"
                  for i in range(entry_count)]
        lines = "\n".join(lines)
        with open(self.filename, "w") as fil:
            fil.write(lines)

    def test_create_dummy_agency(self) -> None:
        agency = GTFSAgency()
        self.assertEqual(1, len(agency.entries))
        self.assertTrue(isinstance(agency.entries[0], DummyGTFSAgencyEntry))

    def test_read_agency(self) -> None:
        self._create_agency(1)
        agency = GTFSAgency()
        self.assertEqual(1, len(agency.entries))
        entry = agency.entries[0]
        self.assertFalse(isinstance(entry, DummyGTFSAgencyEntry))
        self.assertEqual(entry.agency_id, "0")
        self.assertEqual(entry.agency_name, "agency_0")
        self.assertEqual(entry.agency_url, "https://www.pdf2gtfs.com/0")
        self.assertEqual(entry.agency_timezone, "Europe/Berlin")
