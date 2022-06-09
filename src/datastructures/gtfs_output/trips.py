from dataclasses import dataclass
from typing import Callable, TypeAlias, Optional

from datastructures.gtfs_output.base import (BaseContainer,
                                             BaseDataClass)


Trip_Factory: TypeAlias = Callable[[Optional["TripEntry"]], "TripEntry"]


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
        service and route. If entry is given instead removes said entry. """

        def factory(entry: TripEntry | None = None):
            if entry is None:
                return self.add(route_id, service_id)
            self.remove(entry)

        return factory
