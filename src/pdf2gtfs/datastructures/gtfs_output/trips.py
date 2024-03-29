""" Used by the handler to create the file 'trips.txt'. """

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, TYPE_CHECKING, TypeAlias

import pandas as pd

from pdf2gtfs.datastructures.gtfs_output import BaseContainer, BaseDataClass


if TYPE_CHECKING:
    from pdf2gtfs.datastructures.gtfs_output.stop_times import GTFSStopTimes

Trip_Factory: TypeAlias = Callable[[], "GTFSTripsEntry"]


@dataclass(init=False)
class GTFSTripsEntry(BaseDataClass):
    """ A single trip. """
    trip_id: str
    route_id: str
    service_id: str

    def __init__(self, route_id: str, service_id: str, trip_id: str = None
                 ) -> None:
        super().__init__(trip_id)
        self.trip_id = self.id
        self.route_id = route_id
        self.service_id = service_id

    @staticmethod
    def from_series(s: pd.Series) -> GTFSTripsEntry:
        """ Creates a new GTFSTrip from the given series. """
        return GTFSTripsEntry(s["route_id"], s["service_id"], s["trip_id"])


class GTFSTrips(BaseContainer):
    """ Used to create the 'trips.txt'. """
    entries: list[GTFSTripsEntry]

    def __init__(self, path: Path) -> None:
        super().__init__("trips.txt", GTFSTripsEntry, path)

    def add(self, route_id: str, service_id: str) -> GTFSTripsEntry:
        """ Add a single trip with the given route_id and service_id. """
        entry = GTFSTripsEntry(route_id, service_id)
        return self._add(entry)

    def remove(self, entry: GTFSTripsEntry) -> None:
        """ Remove the given entry. """
        if entry in self.entries:
            self.entries.remove(entry)

    def get_factory(self, service_id: str, route_id: str) -> Trip_Factory:
        """ Returns a function which creates a new TripEntry for the given
        service and route. """

        def _trip_factory() -> GTFSTripsEntry:
            return self.add(route_id, service_id)

        return _trip_factory

    def remove_unused(self, stop_times: GTFSStopTimes) -> None:
        """ Removes trips, which are not used by any stop_times entries. """
        trip_ids = {entry.trip_id for entry in stop_times.entries}
        for entry in list(self.entries):
            if entry.trip_id in trip_ids:
                continue
            self.entries.remove(entry)

    def get_with_route_id(self, route_id: str) -> list[GTFSTripsEntry]:
        """ Return all trips with the given route_id. """
        trips = []
        for trip in self.entries:
            if trip.route_id == route_id:
                trips.append(trip)
        return trips
