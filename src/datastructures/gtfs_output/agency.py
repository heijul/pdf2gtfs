""" Classes used by the handler to create the file 'agency.txt'. """

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from datastructures.gtfs_output.__init__ import (
    BaseDataClass, ExistingBaseContainer)
from user_input.cli import select_agency


@dataclass
class AgencyEntry(BaseDataClass):
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
    def from_series(series: pd.Series) -> AgencyEntry:
        """ Return an entry, using the series' values. """
        return AgencyEntry(series["agency_name"],
                           series["agency_url"],
                           series["agency_timezone"],
                           agency_id=series["agency_id"])

    @property
    def values(self) -> list[str]:
        """ Return all values, of this agency. """
        return [self.agency_id, self.agency_name,
                self.agency_url, self.agency_timezone]


class DummyAgencyEntry(AgencyEntry):
    """ Dummy agency, which will be used, if no agency is given. """
    entries: list[AgencyEntry]

    def __init__(self) -> None:
        super().__init__("pdf2gtfs", "", "Europe/Berlin")
        self.name = "pdf2gtfs"


class Agency(ExistingBaseContainer):
    """ Used to create 'agency.txt'. """
    def __init__(self) -> None:
        super().__init__("agency.txt", AgencyEntry)

    def from_file(self, default=None) -> list[AgencyEntry]:
        """ Return the entries, of the existing file if it exists, otherwise
        return a dummy. """
        return super().from_file([DummyAgencyEntry()])

    def get_default(self) -> AgencyEntry:
        """ Return the first agency, if only a single one exists.
        Otherwise, let the user select the correct agency. """
        if len(self.entries) == 1:
            return self.entries[0]
        return select_agency(self.fp, self.entries)
