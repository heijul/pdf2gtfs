from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from config import Config
from datastructures.gtfs_output.__init__ import (
    BaseDataClass, BaseContainer)


@dataclass
class AgencyEntry(BaseDataClass):
    agency_id: str
    agency_name: str
    agency_url: str
    agency_timezone: str

    def __init__(self, name: str, url: str, timezone: str, *, agency_id=None):
        super().__init__()
        self.agency_id = agency_id if agency_id else self.id
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


class Agency(BaseContainer):
    def __init__(self):
        super().__init__("agency.txt", AgencyEntry)

    def add(self):
        # FEATURE: Get data from config/Never overwrite existing agency/etc...
        entries = self.from_file()
        for entry in entries:
            self._add(entry)

    def from_file(self) -> list[AgencyEntry]:
        path = Path(Config.output_dir).resolve()
        if not path.exists() or not self.get_filepath(path).exists():
            return [DummyAgencyEntry()]
        entries = self.entries_from_df(pd.read_csv(self.get_filepath(path)))
        return entries

    @staticmethod
    def entries_from_df(df: pd.DataFrame) -> list[AgencyEntry]:
        print(df)
        entries = []
        for _, values in df.iterrows():
            entries.append(AgencyEntry.from_series(values))
        return entries

    def write(self, path: Path) -> None:
        """ Never overwrite agency. """
        fp = self.get_filepath(path)
        if fp.exists():
            return
        super().write(path)
