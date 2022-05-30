from dataclasses import dataclass

from datastructures.gtfs_output.basestructures import (BaseContainer,
                                                       BaseDataClass)


@dataclass
class Trip(BaseDataClass):
    route_id: int
    service_id: int


class Trips(BaseContainer):
    def __init__(self):
        super().__init__("trips.txt", Trip)
    trips: list[Trip]
