""" Used by the handler to create the file 'stops.txt'. """

from __future__ import annotations

import logging
from dataclasses import dataclass, Field
from enum import IntEnum
from pathlib import Path

import pandas as pd

from pdf2gtfs.config import Config
from pdf2gtfs.datastructures.gtfs_output import BaseContainer, BaseDataClass
from pdf2gtfs.utils import normalize_name


MAX_EDIT_DISTANCE = 3
logger = logging.getLogger(__name__)


# TODO: Add docstrings.
# TODO: If possible, add baseclass for PublicTransport/WheelchairBoarding


class PublicTransport(IntEnum):
    stop_position = 0
    stop_area = 0
    platform = 0
    stop = 0
    station = 1
    train_station = 1
    entrance = 2
    entrance_pass = 2
    generic_node = 3
    boarding_area = 4

    def to_output(self) -> str:
        return str(self.value)

    @staticmethod
    def from_name(name: str) -> PublicTransport:
        if not name:
            return PublicTransport.stop_position
        for public_transport in PublicTransport:
            if public_transport.name.lower() == name.lower():
                return public_transport
        return PublicTransport.stop_position

    @staticmethod
    def from_value(value: int | str | None) -> PublicTransport:
        default = PublicTransport.stop_position
        if value is None:
            return default
        try:
            int_value = int(value)
        except (ValueError, TypeError):
            return default
        for public_transport in PublicTransport:
            if public_transport.value == int_value:
                return public_transport
        return default


class WheelchairBoarding(IntEnum):
    unknown = 0
    yes = 1
    limited = 1
    no = 2

    def to_output(self) -> str:
        return str(self.value)

    @staticmethod
    def from_name(name: str) -> WheelchairBoarding:
        default = WheelchairBoarding.unknown
        if not name:
            return default
        for wheelchair_boarding in WheelchairBoarding:
            if wheelchair_boarding.name.lower() == name.lower():
                return wheelchair_boarding
        return default

    @staticmethod
    def from_value(value: int | str | None) -> WheelchairBoarding:
        default = WheelchairBoarding.unknown
        if value is None:
            return default
        try:
            int_value = int(value)
        except (ValueError, TypeError):
            return default
        for wheelchair_boarding in WheelchairBoarding:
            if wheelchair_boarding.value == int_value:
                return wheelchair_boarding
        return default


@dataclass(init=False)
class GTFSStopEntry(BaseDataClass):
    """ A single stop. """
    stop_id: str
    stop_name: str
    stop_lat: float | None
    stop_lon: float | None
    stop_desc: str
    wheelchair_boarding: WheelchairBoarding
    public_transport: PublicTransport

    def __init__(self, name: str, stop_id: str = None) -> None:
        super().__init__(stop_id)
        self.stop_id = self.id
        self.stop_name = name
        self.normalized_name = normalize_name(name)
        self.stop_lat = None
        self.stop_lon = None
        self.stop_desc = ""
        self.used_in_timetable = False
        self.wheelchair_boarding = WheelchairBoarding.unknown
        self.public_transport = PublicTransport.stop_position

    @property
    def valid(self) -> bool:
        """ Whether the GTFSStop has both a name and a location. """
        return (self.stop_name and
                self.stop_lat is not None
                and self.stop_lon is not None)

    def set_location(self, lat: float | None, lon: float | None,
                     missing: bool) -> None:
        """ Set the location to the given latitude/longitude. """
        interpolate = Config.interpolate_missing_locations
        if (missing and not interpolate) or lat is None or lon is None:
            lat = None
            lon = None
        self.stop_lat = lat
        self.stop_lon = lon
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
    def from_series(s: pd.Series) -> GTFSStopEntry:
        """ Creates a new GTFSStop from the given series. """
        stop = GTFSStopEntry(s["stop_name"], s["stop_id"])
        try:
            lat = float(s["stop_lat"])
            lon = float(s["stop_lon"])
        except (ValueError, KeyError):
            lat = None
            lon = None
        stop.set_location(lat, lon, False)
        stop.stop_desc = s.get("stop_desc")
        stop.wheelchair_boarding = WheelchairBoarding.from_value(
            s.get("wheelchair_boarding"))
        stop.public_transport = PublicTransport.from_value(
            s.get("public_transport"))
        return stop


class GTFSStops(BaseContainer):
    """ Used to create the 'stops.txt'. """
    entries: list[GTFSStopEntry]

    def __init__(self, path: Path) -> None:
        super().__init__("stops.txt", GTFSStopEntry, path)

    def add(self, stop_name: str) -> None:
        """ Add a GTFSStop with the given stop_name. """
        entry = self.get(stop_name)
        if entry:
            entry.used_in_timetable = True
            return
        entry = GTFSStopEntry(stop_name)
        entry.used_in_timetable = True
        super()._add(entry)

    def get(self, stop_name: str) -> GTFSStopEntry:
        """ Return the GTFSStop with the given stop_name. """
        for entry in self.entries:
            if entry.normalized_name != normalize_name(stop_name):
                continue
            return entry

    def get_by_stop_id(self, stop_id: str) -> GTFSStopEntry:
        """ Return the GTFSStop with the given stop_id.

        If no such GTFSStop exists, a KeyError is raised.
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
