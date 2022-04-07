from dataclasses import dataclass, field

from datastructures.basestructures import UIDDataClass, BaseContainer
from datastructures.stop import Stop


@dataclass
class Route(UIDDataClass):
    name: str
    stops: list[Stop] = field(default_factory=list)

    def __init__(self, name: str) -> None:
        super().__init__()
        # TODO: route_type + agency + name?
        self.name = name
        self.stops: list[Stop] = list()
        Routes.add(self)

    def add_stop(self, stop: Stop, index: int = -1):
        if index == -1:
            index = len(self.stops)
        self.stops.insert(index, stop)


class Routes(BaseContainer):
    pass
