from dataclasses import dataclass

from datastructures.gtfs_output.basestructures import (BaseContainer,
                                                       BaseDataClass)


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
    entries: dict[int, TripEntry]

    def __init__(self):
        super().__init__("trips.txt", TripEntry)

    def add(self, route_id: int, service_id: int) -> TripEntry:
        entry = TripEntry(route_id, service_id)
        self._add(entry)
        return entry
