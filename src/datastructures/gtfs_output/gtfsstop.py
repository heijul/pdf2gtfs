from dataclasses import dataclass
from operator import itemgetter

from datastructures.gtfs_output.__init__ import (
    BaseDataClass, BaseContainer)


MAX_EDIT_DISTANCE = 3


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

    def set_location(self, lat: float, lon: float) -> None:
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

    def get(self, name) -> GTFSStop:
        for entry in self.entries:
            if entry.stop_name != name:
                continue
            return entry

    def get_closest(self, name: str) -> tuple[int, GTFSStop | None]:
        dists: list[tuple[int, GTFSStop]] = []
        for entry in self.entries:
            dist = self._get_edit_distance(entry.stop_name, name)
            if dist > MAX_EDIT_DISTANCE:
                continue
            dists.append((dist, entry))
        return min(dists, key=itemgetter(0), default=(0, None))

    @staticmethod
    def _get_edit_distance(s1, s2):
        """ Uses the Wagner-Fischer Algorithm. """
        s1 = " " + s1.casefold().lower()
        s2 = " " + s2.casefold().lower()
        m = len(s1)
        n = len(s2)
        d = [[0] * n for _ in range(m)]

        for i in range(1, m):
            d[i][0] = i
        for j in range(1, n):
            d[0][j] = j

        for j in range(1, n):
            for i in range(1, m):
                cost = int(s1[i] != s2[j])
                d[i][j] = min(d[i - 1][j] + 1,
                              d[i][j - 1] + 1,
                              d[i - 1][j - 1] + cost)

        return d[m - 1][n - 1]
