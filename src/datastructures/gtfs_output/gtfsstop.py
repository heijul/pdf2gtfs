from dataclasses import dataclass

from datastructures.gtfs_output.base import (
    BaseDataClass, BaseContainer)


@dataclass(init=False)
class GTFSStop(BaseDataClass):
    stop_id: int
    stop_name: str
    stop_lat: float
    stop_lon: float

    def __init__(self, name: str, lat: float = -1, lon: float = -1):
        super().__init__()
        self.stop_id = self.id
        self.stop_name = name.strip()
        self.stop_lat = lat
        self.stop_lon = lon


class GTFSStops(BaseContainer):
    entries: list[GTFSStop]

    def __init__(self):
        super().__init__("stops.txt", GTFSStop)

    def add(self, stop_name: str) -> None:
        if self.get(stop_name):
            return
        super()._add(GTFSStop(stop_name))

    def get(self, name):
        for entry in self.entries:
            if entry.stop_name != name:
                continue
            return entry