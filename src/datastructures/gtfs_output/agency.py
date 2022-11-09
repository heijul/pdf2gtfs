""" Classes used by the handler to create the file 'agency.txt'. """

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from datastructures.gtfs_output.__init__ import BaseDataClass, BaseContainer


@dataclass
class GTFSAgencyEntry(BaseDataClass):
    """ A single agency. """
    agency_id: str
    agency_name: str
    agency_url: str
    agency_timezone: str

    def __init__(self, name: str, url: str, timezone: str,
                 *, agency_id: str = None):
        super().__init__(agency_id)
        self.agency_id = self.id
        self.agency_name = name
        self.agency_url = url
        self.agency_timezone = timezone

    @staticmethod
    def from_series(series: pd.Series) -> GTFSAgencyEntry:
        """ Return an entry, using the series' values. """
        return GTFSAgencyEntry(series["agency_name"],
                               series["agency_url"],
                               series["agency_timezone"],
                               agency_id=series["agency_id"])

    @property
    def values(self) -> list[str]:
        """ Return all values, of this agency. """
        return [self.agency_id, self.agency_name,
                self.agency_url, self.agency_timezone]


class DummyGTFSAgencyEntry(GTFSAgencyEntry):
    """ Dummy agency, which will be used, if no agency is given. """
    entries: list[GTFSAgencyEntry]

    def __init__(self) -> None:
        super().__init__(
            "pdf2gtfs", "https://www.example.com", "Europe/Berlin")
        self.name = "pdf2gtfs"


class GTFSAgency(BaseContainer):
    """ Used to create 'agency.txt'. """

    def __init__(self, outdir: Path) -> None:
        super().__init__("agency.txt", GTFSAgencyEntry, outdir)

    def read_input_files(self) -> list[GTFSAgencyEntry]:
        """ Return the entries of the inputfiles, otherwise return a dummy. """
        entries = super().read_input_files()
        if not entries:
            return [DummyGTFSAgencyEntry()]
        return entries
