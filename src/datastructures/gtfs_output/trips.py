from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, TypeAlias, TYPE_CHECKING

from datastructures.gtfs_output.__init__ import (BaseContainer,
                                                 BaseDataClass)

if TYPE_CHECKING:
    from datastructures.gtfs_output.stop_times import StopTimes


Trip_Factory: TypeAlias = Callable[[], "TripEntry"]


@dataclass(init=False)
class TripEntry(BaseDataClass):
    trip_id: int
    route_id: int
    service_id: int

    def __init__(self, route_id, service_id):
        super().__init__()
        self.trip_id = self.id
        self.route_id = route_id
        self.service_id = service_id


class Trips(BaseContainer):
    entries: list[TripEntry]

    def __init__(self):
        super().__init__("trips.txt", TripEntry)

    def add(self, route_id: int, service_id: int) -> TripEntry:
        entry = TripEntry(route_id, service_id)
        self._add(entry)
        return entry

    def remove(self, entry: TripEntry) -> None:
        if entry in self.entries:
            self.entries.remove(entry)

    def get_factory(self, service_id, route_id) -> Trip_Factory:
        """ Returns a function which creates a new TripEntry for the given
        service and route. """

        def factory() -> TripEntry:
            return self.add(route_id, service_id)

        return factory

    def remove_unused(self, stop_times: StopTimes) -> None:
        """ Removes trips, which are not used by any stop_times entries. """
        trip_ids = {entry.trip_id for entry in stop_times.entries}
        for entry in list(self.entries):
            if entry.trip_id in trip_ids:
                continue
            self.entries.remove(entry)
