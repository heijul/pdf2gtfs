from typing import ClassVar

from stop import Stop


class Schedule:
    stops: ClassVar[list[Stop]] = []

    def add_stop(self, stop: Stop) -> None:
        self.stops.append(stop)

    def add_stop_raw(self, name, location):
        self.add_stop(Stop(name, location))
