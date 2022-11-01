""" Used by the handler to create the file 'stops.txt'. """

from __future__ import annotations

import logging
from dataclasses import dataclass, Field

import pandas as pd

from config import Config
from datastructures.gtfs_output import BaseDataClass, ExistingBaseContainer
from utils import normalize_name


MAX_EDIT_DISTANCE = 3
logger = logging.getLogger(__name__)


@dataclass(init=False)
class GTFSStopEntry(BaseDataClass):
    """ A single stop. """
    stop_id: str
    stop_name: str
    stop_lat: float | None
    stop_lon: float | None
    stop_desc: str

    def __init__(self, name: str, *, stop_id: str = None) -> None:
        super().__init__(stop_id)
        self.stop_id = self.id
        self.stop_name = name
        self.normalized_name = normalize_name(name)
        self._stop_lat = None
        self._stop_lon = None
        self.stop_desc = ""
        self.used_in_timetable = False

    @property
    def stop_lat(self) -> float | None:
        """ The latitude of the GTFSStop. """
        return self._stop_lat

    @property
    def stop_lon(self) -> float | None:
        """ The longitude of the GTFSStop. """
        return self._stop_lon

    @property
    def valid(self) -> bool:
        """ Whether the GTFSStop has both a name and a location. """
        return (self.stop_name and
                self.stop_lat is not None
                and self.stop_lon is not None)

    def set_location(self, lat: float, lon: float, missing: bool) -> None:
        """ Set the location to the given latitude/longitude. """
        interpolate = Config.interpolate_missing_locations
        if (missing and not interpolate) or lat is None or lon is None:
            lat = None
            lon = None
        self._stop_lat = lat
        self._stop_lon = lon
        if missing and interpolate:
            self.stop_desc = ("Location interpolated by pdf2gtfs using "
                              "the surrounding locations.")

    def get_field_value(self, field: Field):
        """ Clean either coordinate value, if it is None. """
        if field in ["stop_lat", "stop_lon"]:
            value = super().get_field_value(field)
            return "" if value is None else value
        return super().get_field_value(field)

    @staticmethod
    def from_series(series: pd.Series) -> GTFSStopEntry:
        """ Creates a new GTFSStop from the given series. """
        stop = GTFSStopEntry(series["stop_name"], stop_id=series["stop_id"])
        stop.set_location(series.get("stop_lat"), series.get("stop_lon"),
                          False)
        stop.stop_desc = series.get("stop_desc")
        return stop


class GTFSStops(ExistingBaseContainer):
    """ Used to create the 'stops.txt'. """
    entries: list[GTFSStopEntry]

    def __init__(self) -> None:
        super().__init__("stops.txt", GTFSStopEntry)
        self.append = False
        self.new_entries = []

    def to_output(self) -> str:
        """ Return the content of the gtfs file. """
        if not self.append:
            return super().to_output()
        with open(self.fp) as fil:
            old_entries = fil.read().strip()
        new_entries = "\n".join([e.to_output() for e in self.new_entries])
        return f"{old_entries}\n{new_entries}\n"

    def write(self) -> None:
        """ Write the file to the disk.

        New entries will be appended, if necessary. """
        if self.new_entries:
            stops = "\n\t".join([e.stop_name for e in self.new_entries])
            stops = f"\n\t{stops}\n"
            logger.warning(
                f"The file '{self.filename}' exists and contains data, but "
                f"does not contain entries for the following stops:{stops}"
                f"\nNew entries will be created and added to the file.")
            self.overwrite = True
        super().write()

    def add(self, stop_name: str) -> None:
        """ Add a GTFSStop with the given stop_name. """
        entry = self.get(stop_name)
        if entry:
            entry.used_in_timetable = True
            return
        entry = GTFSStopEntry(stop_name)
        entry.used_in_timetable = True
        if self.fp.exists() and not self.overwrite:
            self.append = True
            self.new_entries.append(entry)
        super()._add(entry)

    def get(self, stop_name: str) -> GTFSStopEntry:
        """ Return the GTFSStop with the given stop_name. """
        for entry in self.entries:
            if entry.normalized_name != stop_name:
                continue
            return entry

    def get_by_stop_id(self, stop_id: str) -> GTFSStopEntry:
        """ Return the GTFSStop with the given stop_id.

        If no such GTFSStop exists, will either return None or raise a
        KeyError, depending on missing_ok.
        """
        for entry in self.entries:
            if entry.stop_id == stop_id:
                return entry
        raise KeyError(f"No stop with stop_id '{stop_id}'.")

    def get_existing_stops(self, stop_ids: list[str]
                           ) -> dict[str: tuple[float, float]]:
        """ Return the locations of any existing stops of route. """
        existing_locs: dict[str: tuple[float, float]] = {}

        for stop_id in stop_ids:
            try:
                gtfs_stop = self.get_by_stop_id(stop_id)
            except KeyError:
                continue
            existing_locs[stop_id] = gtfs_stop.stop_lat, gtfs_stop.stop_lon

        return existing_locs
