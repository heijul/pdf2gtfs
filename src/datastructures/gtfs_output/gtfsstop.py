""" Used by the handler to create the file 'stops.txt'. """

from __future__ import annotations

import logging
from dataclasses import dataclass, Field

import pandas as pd

from datastructures.gtfs_output import BaseDataClass, ExistingBaseContainer


MAX_EDIT_DISTANCE = 3
logger = logging.getLogger(__name__)


@dataclass(init=False)
class GTFSStop(BaseDataClass):
    """ A single stop. """
    stop_id: str
    stop_name: str
    stop_lat: float | None
    stop_lon: float | None

    def __init__(self, name: str, *, stop_id: str = None) -> None:
        super().__init__(stop_id)
        self.stop_id = self.id
        self.stop_name = name
        self._stop_lat = None
        self._stop_lon = None

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

    def set_location(self, lat: float, lon: float) -> None:
        """ Set the location to the given latitude/longitude. """
        if lat is None or lon is None:
            lat = None
            lon = None
        self._stop_lat = lat
        self._stop_lon = lon

    def _to_output(self, field: Field) -> str:
        is_coordinate_field = field in ["stop_lat", "stop_lon"]
        if is_coordinate_field and self.get_field_value(field) is None:
            return ""
        return super()._to_output(field)

    @staticmethod
    def from_series(series: pd.Series) -> GTFSStop:
        """ Creates a new GTFSStop from the given series. """
        stop = GTFSStop(series["stop_name"], stop_id=series["stop_id"])
        stop.set_location(series.get("stop_lat"), series.get("stop_lon"))
        return stop


class GTFSStops(ExistingBaseContainer):
    """ Used to create the 'stops.txt'. """
    entries: list[GTFSStop]

    def __init__(self) -> None:
        super().__init__("stops.txt", GTFSStop)
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
        """ Writes the file to the disk, appending new entries if necessary. """
        if self.new_entries:
            stops = "', '".join([e.stop_name for e in self.new_entries])
            stops = f"['{stops}']"
            logger.warning(
                f"The file '{self.filename}' exists and contains data, but "
                f"does not contain entries for the following stops:\n{stops}"
                f"\nNew entries will be created and added to the file.")
            self.overwrite = True
        super().write()

    def add(self, stop_name: str) -> None:
        """ Add a GTFSStop with the given stop_name. """
        if self.get(stop_name):
            return
        entry = GTFSStop(stop_name)
        if self.fp.exists() and not self.overwrite:
            self.append = True
            self.new_entries.append(entry)
        super()._add(entry)

    def get(self, stop_name: str) -> GTFSStop:
        """ Return the GTFSStop with the given stop_name. """
        for entry in self.entries:
            # TODO: Normalize both names.
            if entry.stop_name != stop_name:
                continue
            return entry

    def get_by_stop_id(self, stop_id: str) -> GTFSStop:
        """ Return the GTFSStop with the given stop_id.
        Raises a KeyError if no such GTFSStop exists. """
        for entry in self.entries:
            if entry.stop_id == stop_id:
                return entry
        raise KeyError(f"No stop with stop_id '{stop_id}'.")
