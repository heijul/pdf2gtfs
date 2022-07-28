from dataclasses import dataclass

from datastructures.gtfs_output.__init__ import (
    BaseDataClass, BaseContainer)


@dataclass
class AgencyEntry(BaseDataClass):
    agency_id: str
    agency_name: str
    agency_url: str
    agency_timezone: str

    def __init__(self, name: str, url: str, timezone: str):
        super().__init__()
        self.agency_id = self.id
        self.agency_name = name
        self.agency_url = url
        self.agency_timezone = timezone


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
        entry = DummyAgencyEntry()
        self._add(entry)
