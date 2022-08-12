from __future__ import annotations

import logging
from dataclasses import dataclass
from operator import itemgetter

import pandas as pd

from datastructures.gtfs_output.__init__ import (
    BaseDataClass, ExistingBaseContainer)
from utils import get_edit_distance


MAX_EDIT_DISTANCE = 3
logger = logging.getLogger(__name__)


@dataclass(init=False)
class GTFSStop(BaseDataClass):
    stop_id: int
    stop_name: str
    stop_lat: float
    stop_lon: float

    def __init__(self, name: str, lat: float = -1, lon: float = -1,
                 *, stop_id=None):
        super().__init__()
        self.stop_id = self.id if stop_id is None else stop_id
        self.stop_name = name.strip()
        self.stop_lat = lat
        self.stop_lon = lon

    def set_location(self, lat: float, lon: float) -> None:
        self.stop_lat = lat
        self.stop_lon = lon

    def to_output(self) -> str:
        return (f"{self.stop_id},\"{self.stop_name}\","
                f"{self.stop_lat},{self.stop_lon}")

    @staticmethod
    def from_series(series: pd.Series) -> GTFSStop:
        return GTFSStop(series["stop_name"],
                        series["stop_lat"],
                        series["stop_lon"],
                        stop_id=series["stop_id"])


class GTFSStops(ExistingBaseContainer):
    entries: list[GTFSStop]

    def __init__(self):
        super().__init__("stops.txt", GTFSStop)

    def add(self, stop_name: str) -> None:
        if self.get(stop_name):
            return
        if self.fp.exists() and not self.overwrite:
            logger.warning(
                f"The file '{self.fp}' exists and contains data, but does "
                f"not contain a stop for '{stop_name}'. A new entry will "
                f"be created.")
        super()._add(GTFSStop(stop_name))

    def get(self, name) -> GTFSStop:
        for entry in self.entries:
            if entry.stop_name != name:
                continue
            return entry

    def get_closest(self, name: str) -> tuple[int, GTFSStop | None]:
        dists: list[tuple[int, GTFSStop]] = []
        for entry in self.entries:
            dist = get_edit_distance(entry.stop_name, name)
            if dist > MAX_EDIT_DISTANCE:
                continue
            dists.append((dist, entry))
        return min(dists, key=itemgetter(0), default=(0, None))
