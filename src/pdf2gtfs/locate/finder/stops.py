""" Stops used by the locate. """

from __future__ import annotations

from typing import Iterator, TYPE_CHECKING

import pdf2gtfs.locate.finder.loc_nodes as loc_nodes
from pdf2gtfs.config import Config
from pdf2gtfs.datastructures.gtfs_output.stop import GTFSStopEntry
from pdf2gtfs.datastructures.gtfs_output.stop_times import Time


if TYPE_CHECKING:
    from pdf2gtfs.datastructures.gtfs_output.handler import GTFSHandler


def get_travel_distance(avg_time: Time) -> float:
    """ Return the distance travelled (in m), using the average speed and time.

    Uses the average time to the next stop and the average speed
     to calculate the maximal distance.
    Speed is in km/h and we multiply it by hours, so we need to
     multiply by 1000 again to get the distance in meters.
    """
    return avg_time.to_hours() * Config.average_speed * 1000


class Stop:
    """ A stop, uniquely defined by its GTFS stop_id, name and route index. """
    stops: Stops = None

    def __init__(self, idx: int, stop_id: str, name: str) -> None:
        self.idx = idx
        self.stop_id = stop_id
        self.name = name
        self.nodes = []
        self._next = None
        self._max_dist_to_next = None
        self.distance_bounds = self._get_distance_bounds()
        if Stop.stops is None:
            raise Exception("Stop.stops needs to be, before creating a Stop.")

    @property
    def exists(self) -> bool:
        """ Checks if any of the nodes exists already. """
        return any(isinstance(node, loc_nodes.ENode) for node in self.nodes)

    @property
    def is_first(self) -> bool:
        """ Whether the stop is the first stop of the route. """
        return self is self.stops.first

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
        # Need to recalculate the bounds if the next stop changes.
        self.distance_bounds = self._get_distance_bounds()

    def _get_distance_bounds(self) -> tuple[float, float, float]:
        """ Set the lower/mid/upper distance limits.

        The mid limit is defined using the average travel time and speed.
        The lower and upper limits are defined using the average trave speed
        and the travel time, offset by (arbitrarily chosen) 2 minutes.
        The lower bound can't be lower than the min_travel_distance..
        """
        time_delta = Time(0, Config.average_travel_distance_offset)
        if self.next is None:
            return float("inf"), float("inf"), float("inf")
        avg_time = Stop.stops.get_avg_time_between(self, self.next)
        lower = get_travel_distance(avg_time - time_delta)
        mid = get_travel_distance(avg_time)
        upper = get_travel_distance(avg_time + time_delta)
        return (max(lower, Config.min_travel_distance),
                max(mid, Config.min_travel_distance),
                max(upper, Config.min_travel_distance))

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

    def __init__(self, handler: GTFSHandler, route_id: str,
                 gtfs_stops: list[GTFSStopEntry]) -> None:
        self.handler = handler
        self.route_id = route_id
        Stop.stops = self
        self.first, self.last = self._create_stops(gtfs_stops)

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
    def _create_stops(gtfs_stops: list[GTFSStopEntry]) -> tuple[Stop, Stop]:
        """ Create the stops from the gtfs_stops. Returns the start/end. """
        first_stop = None
        previous_stop = None

        for i, gtfs_stop in enumerate(gtfs_stops):
            current_stop = Stop(i, gtfs_stop.stop_id, gtfs_stop.stop_name)
            if not first_stop:
                first_stop = current_stop
            if previous_stop:
                previous_stop.next = current_stop
            previous_stop = current_stop

        return first_stop, previous_stop

    def get_avg_time_between(self, stop1: Stop, stop2: Stop) -> Time:
        """ Return the average time it takes to get from stop1 to stop2. """
        return self.handler.get_avg_time_between_stops(
            self.route_id, stop1.stop_id, stop2.stop_id)

    def __iter__(self) -> Iterator[Stop, None, None]:
        current = self.first
        while current is not None:
            yield current
            current = current.next

    def get_from_stop_id(self, stop_id: str) -> Stop:
        """ Return the Stop with the given stop_id.

        Raises a KeyError, if no Stop with the given stop_id exists.
        """
        stop = self.first
        while stop is not None:
            if stop.stop_id == stop_id:
                return stop
            stop = stop.next
        raise KeyError(f"Stop with stop_id '{stop_id}' does not exist.")
