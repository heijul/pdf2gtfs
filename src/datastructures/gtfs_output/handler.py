from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from datastructures.gtfs_output.route import Routes
from datastructures.gtfs_output.stop import Stops

if TYPE_CHECKING:
    from datastructures.timetable.table import TimeTable


class GTFSHandler:
    def __init__(self):
        self._stops = Stops()
        self._routes = Routes()

    def timetable_to_gtfs(self, timetable: TimeTable):
        print(self)
        print(timetable)
        for stop in timetable.stops.stops:
            self.stops.add(stop.name)
        stop_entries = list(self.stops.entries.values())
        route_name = (f"{stop_entries[0].stop_name}"
                      f"-{stop_entries[-1].stop_name}")
        self.routes.add(route_name)

    def write_files(self):
        print(self)
        path = Path("../gtfs_output/").resolve()
        path.mkdir(exist_ok=True)
        self.stops.write(path)
        self.routes.write(path)

    @property
    def routes(self):
        return self._routes

    @property
    def stops(self):
        return self._stops
