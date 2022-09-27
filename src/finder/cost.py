from __future__ import annotations

from math import inf


class Cost:
    def __init__(self, parent_cost: float = None, node_cost: float = None,
                 name_cost: float = None, travel_cost: float = None,
                 stop_cost: float = None) -> None:
        def _get_cost(cost: float) -> float:
            return inf if cost is None or cost < 0 else cost

        self.parent_cost = _get_cost(parent_cost)
        self.node_cost = _get_cost(node_cost)
        self.name_cost = _get_cost(name_cost)
        self.travel_cost = _get_cost(travel_cost)
        self.stop_cost = _get_cost(stop_cost)

    @property
    def as_float(self) -> float:
        return sum(self.costs)

    @property
    def travel_cost(self) -> float:
        return self._travel_cost

    @travel_cost.setter
    def travel_cost(self, travel_cost: float) -> None:
        if travel_cost != inf:
            travel_cost = min(round(travel_cost), 100)
        self._travel_cost = travel_cost

    @property
    def costs(self) -> tuple[float, float, float, float, float]:
        return (self.parent_cost, self.node_cost,
                self.name_cost, self.travel_cost, self.stop_cost)

    @staticmethod
    def from_cost(cost: Cost) -> Cost:
        return Cost(cost.parent_cost, cost.node_cost,
                    cost.name_cost, cost.travel_cost,
                    cost.stop_cost)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Cost):
            return False
        self_is_inf = self.as_float == inf
        other_is_inf = other.as_float == inf
        # One is inf the other is not.
        if (self_is_inf + other_is_inf) % 2 == 1:
            return not other_is_inf
        if not self_is_inf and not other_is_inf:
            return (self.stop_cost == other.stop_cost and
                    self.as_float == other.as_float)
        return self.as_float == other.as_float

    def __lt__(self, other: Cost) -> bool:
        if not isinstance(other, Cost):
            raise TypeError(
                f"Can only compare Cost to Cost, not {type(object)}.")

        self_is_inf = self.as_float == inf
        other_is_inf = other.as_float == inf
        if not self_is_inf and not other_is_inf:
            if self.as_float == other.as_float:
                return self.stop_cost < other.stop_cost
            return self.as_float < other.as_float
        if (self_is_inf + other_is_inf) % 2 == 1:
            return not self_is_inf and other_is_inf
        return self.costs.count(inf) < other.costs.count(inf)

    def __le__(self, other: Cost) -> bool:
        return self == other or self < other

    def __gt__(self, other: Cost) -> bool:
        return not self <= other

    def __ge__(self, other: Cost) -> bool:
        return not self < other

    def __repr__(self) -> str:
        fmt = ">3.0f"
        return (f"Cost("
                f"total: {self.as_float:{fmt}}, "
                f"parent: {self.parent_cost:{fmt}}, "
                f"node: {self.node_cost:{fmt}}, "
                f"name: {self.name_cost:{fmt}}, "
                f"travel: {self.travel_cost:{fmt}}, "
                f"stop: {self.stop_cost:{fmt}})")


class StartCost(Cost):
    @staticmethod
    def from_cost(cost: Cost) -> Cost:
        s = Cost.from_cost(cost)
        s.parent_cost = 0
        s.travel_cost = 0
        return s
