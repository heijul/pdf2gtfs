from dataclasses import dataclass

from datastructures.gtfs_output.basestructures import (
    UIDDataClass, BaseContainer, ContainerObjectType)
from datastructures.gtfs_output.location import Location


@dataclass(init=False)
class Stop(UIDDataClass):
    name: str
    location: Location | None = None

    def __init__(self, name, location=None):
        super().__init__()
        self.name = name
        self.location = location
        Stops.add(self)

    def set_location(self, location: Location):
        self.location = location


class Stops(BaseContainer):
    _objects: dict[int, ContainerObjectType] = {}

    def __repr__(self):
        return f"{self.__name__!r}: {self._objects!r}"
