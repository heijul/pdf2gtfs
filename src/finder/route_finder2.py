from __future__ import annotations

from collections import abc
from typing import Generator

from config import Config
from datastructures.gtfs_output.handler import GTFSHandler
from datastructures.gtfs_output.stop_times import Time


class Distance:
    def __init__(self, *, m: float = -1, km: float = -1):
        assert m >= 0 or km >= 0
        self.distance = m if m >= 0 else km * 1000

    @property
    def m(self) -> float:
        return self.distance

    @property
    def km(self) -> float:
        return self.distance / 1000

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Distance):
            return False
        return self.distance == other.distance

    def __lt__(self, other: Distance) -> bool:
        if not isinstance(other, Distance):
            raise TypeError(
                f"Can only compare Distance to Distance, not {type(object)}.")
        return self.distance < other.distance

    def __le__(self, other: Distance) -> bool:
        return self == other or self < other

    def __gt__(self, other: Distance) -> bool:
        return self != other and not self < other

    def __ge__(self, other: Distance) -> bool:
        return self == other or self > other


class Stop:
    speed_in_km_h: float = None
    stops: Stops = None

    def __init__(self, idx: int, name: str) -> None:
        self.idx = idx
        self.name = name
        self._next = None
        self._avg_time_to_next = None
        if Stop.speed_in_km_h is None:
            Stop.set_speed()

    @staticmethod
    def set_speed() -> None:
        Stop.speed_in_km_h = Config.average_speed

    @property
    def next(self) -> Stop | None:
        return self._next

    @next.setter
    def next(self, value: Stop) -> None:
        self._next = value

    @property
    def avg_time_to_next_in_h(self) -> float:
        def _calculate_avg_time_to_next() -> Time:
            return Stop.stops.get_avg_time_between(self, self.next)
        if self._avg_time_to_next is None:
            self._avg_time_to_next = _calculate_avg_time_to_next().to_float()
        return self._avg_time_to_next

    def max_dist_to_next(self) -> Distance:
        if not self.next:
            return Distance(m=0)
        return Distance(km=self.avg_time_to_next_in_h * Stop.speed_in_km_h)

    def __hash__(self) -> int:
        return hash(self.idx)


class Stops(abc.Iterator):
    def __init__(self, handler: GTFSHandler, stop_names: list[str]) -> None:
        self.handler = handler
        Stop.stops = self
        self.first: Stop = self._create_stops(stop_names)

    @staticmethod
    def _create_stops(stop_names: list[str]) -> Stop:
        next_ = None
        for idx, stop_name in reversed(list(enumerate(stop_names))):
            stop = Stop(idx, stop_name)
            stop.next = next_
            next_ = stop
        return next_

    def get_avg_time_between(self, stop1: Stop, stop2: Stop) -> Time:
        return self.handler.get_avg_time_between_stops(stop1.idx, stop2.idx)

    @property
    def stops(self) -> list[Stop]:
        stops = []
        current = self.first
        while current is not None:
            stops.append(current)
            current = current.next

        return stops

    def __next__(self) -> Generator[Stop]:
        current = self.first
        while current is not None:
            yield current
        raise StopIteration


class Score:
    def __init__(self, node_score: float = None, name_score: float = None,
                 dist_score: float = None) -> None:
        self.node_score = self._get_score(node_score)
        self.name_score = self._get_score(name_score)
        self.dist_score = self._get_score(dist_score)

    @property
    def score(self) -> float:
        return sum(self.scores)

    @property
    def scores(self) -> tuple[float, float, float]:
        return self.node_score, self.name_score, self.dist_score

    @property
    def invalid(self) -> bool:
        def invalid_score(score: float) -> bool:
            return score is None or score == float("inf")

        return any(map(invalid_score, self.scores))

    @staticmethod
    def _get_score(score: float) -> float:
        return float("inf") if score is None or score < 0 else score

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Score) and self.score == other.score

    def __lt__(self, other: Score) -> bool:
        if not isinstance(other, Score):
            raise TypeError(
                f"Can only compare Score to Score, not {type(object)}.")
        return self.score < other.score

    def __le__(self, other: Score) -> bool:
        return self == other or self < other

    def __gt__(self, other: Score) -> bool:
        return self != other and not self < other

    def __ge__(self, other: Score) -> bool:
        return self == other or self > other
