from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from datastructures.gtfs_output.__init__ import (
    BaseDataClass, ExistingBaseContainer)


@dataclass
class AgencyEntry(BaseDataClass):
    agency_id: str
    agency_name: str
    agency_url: str
    agency_timezone: str

    def __init__(self, name: str, url: str, timezone: str, *, agency_id=None):
        super().__init__()
        self.agency_id = self.id if agency_id is None else agency_id
        self.agency_name = name
        self.agency_url = url
        self.agency_timezone = timezone

    @staticmethod
    def from_series(series: pd.Series) -> AgencyEntry:
        return AgencyEntry(series["agency_name"],
                           series["agency_url"],
                           series["agency_timezone"],
                           agency_id=series["agency_id"])


class DummyAgencyEntry(AgencyEntry):
    entries: list[AgencyEntry]

    def __init__(self):
        super().__init__("pdf2gtfs", "", "Europe/Berlin")
        self.name = "pdf2gtfs"


class Agency(ExistingBaseContainer):
    def __init__(self):
        super().__init__("agency.txt", AgencyEntry)

    def add(self):
        entries = self.from_file()
        for entry in entries:
            self._add(entry)

    def from_file(self, default=None) -> list[AgencyEntry]:
        return super().from_file([DummyAgencyEntry()])
