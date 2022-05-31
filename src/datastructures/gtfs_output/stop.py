from dataclasses import dataclass

from datastructures.gtfs_output.basestructures import (
    BaseDataClass, BaseContainer)


@dataclass(init=False)
class Stop(BaseDataClass):
    stop_id: str
    stop_name: str
    stop_lat: float
    stop_lon: float

    def __init__(self, name: str, lat: float = -1, lon: float = -1):
        super().__init__()
        self.stop_id = str(self.id)
        self.stop_name = name.strip()
        self.stop_lat = lat
        self.stop_lon = lon


class Stops(BaseContainer):
    entries: dict[int, Stop] = {}

    def __init__(self):
        super().__init__("stops.txt", Stop)

    def add(self, stop_name: str) -> None:
        if self.get_from_name(stop_name):
            return
        super()._add(Stop(stop_name))

    def get_from_name(self, name):
        for entry in self.entries.values():
            if entry.stop_name != name:
                continue
            return entry
