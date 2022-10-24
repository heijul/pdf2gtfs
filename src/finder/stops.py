""" Stops used by the finder. """

from __future__ import annotations

from typing import Generator, TYPE_CHECKING

from config import Config
from datastructures.gtfs_output.stop_times import Time
from finder.distance import Distance


if TYPE_CHECKING:
    from datastructures.gtfs_output.handler import GTFSHandler


class Stop:
    """ A stop, uniquely defined by its GTFS stop_id, name and route index. """
    stops: Stops = None

    def __init__(self, idx: int, stop_id: str, name: str,
                 next_: Stop | None, stop_cost: int) -> None:
        self.idx = idx
        self.stop_id = stop_id
        self.name = name
        self._next = next_
        self.cost = stop_cost
        self._avg_time_to_next = None
        self._max_dist_to_next = None
        self._set_distance_bounds()

    @property
    def is_last(self) -> bool:
        """ Whether the stop is the last stop of the route. """
        return self is self.stops.last

    @property
    def next(self) -> Stop | None:
        """ The next stop in the route.

        If the current stop is the last stop, return None instead.
        """
        return self._next

    @next.setter
    def next(self, value: Stop) -> None:
        self._next = value

    @property
    def avg_time_to_next(self) -> Time:
        """ The average (as written in the pdf timetable) time it takes to
        get to the next stop of the route. """

        def _calculate_avg_time_to_next() -> Time:
            return Stop.stops.get_avg_time_between(self, self.next)

        if self._avg_time_to_next is None and self.next:
            self._avg_time_to_next: Time = _calculate_avg_time_to_next()
        return self._avg_time_to_next

    @staticmethod
    def get_max_dist(avg_time: Time) -> Distance:
        """ Uses the average time to the next stop and the average speed
        to calculate the maximal distance. """
        return Distance(km=avg_time.to_hours() * Config.average_speed)

    def _set_distance_bounds(self) -> None:
        if self.avg_time_to_next is None:
            self.distance_bounds = Distance(m=0), Distance(m=0)
            return

        lower = self.get_max_dist(self.avg_time_to_next - Time(0, 1))
        upper = self.get_max_dist(self.avg_time_to_next + Time(0, 1))
        self.distance_bounds = lower, upper

    @property
    def max_dist_to_next(self) -> Distance:
        """ The approximate maximal distance the next stop is away. """
        if not self._max_dist_to_next:
            self._max_dist_to_next = self.get_max_dist(self.avg_time_to_next)
        return self._max_dist_to_next

    def before(self, other: Stop) -> bool:
        """ Return True, if this stop occurs before other. """
        return self.idx < other.idx

    def after(self, other: Stop) -> bool:
        """ Return True, if this stop occurs after other. """
        return self.idx > other.idx

    def __hash__(self) -> int:
        return hash(self.stop_id)

    def __repr__(self) -> str:
        return f"Stop({self.stop_id}, '{self.name}')"


class Stops:
    """ The stops of a route. Implemented as singly-linked-list. """

    def __init__(self, handler: GTFSHandler,
                 stop_names: list[tuple[str, str]]) -> None:
        self.handler = handler
        Stop.stops = self
        self.first, self.last = self._create_stops(stop_names)

    @property
    def stops(self) -> list[Stop]:
        """ The specific Stop objects the route consists of. """
        stops = []
        current = self.first
        while current is not None:
            stops.append(current)
            current = current.next

        return stops

    @staticmethod
    def _create_stops(stop_names: list[tuple[str, str]]) -> tuple[Stop, Stop]:
        last = None
        stop = None
        names_with_index = [(idx, s_id, name)
                            for idx, (s_id, name) in enumerate(stop_names)]

        for i, idx, stop_name in reversed(names_with_index):
            stop = Stop(i, idx, stop_name, stop, i * 1000)
            if not last:
                last = stop

        return stop, last

    def get_avg_time_between(self, stop1: Stop, stop2: Stop) -> Time:
        """ Return the average time it takes to get from stop1 to stop2. """
        # TODO NOW: Uses all routes. Should instead use the current route.
        return self.handler.get_avg_time_between_stops(
            stop1.stop_id, stop2.stop_id)

    def __iter__(self) -> Generator[Stop, None, None]:
        current = self.first
        while current is not None:
            yield current
            current = current.next
