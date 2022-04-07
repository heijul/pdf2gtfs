from dataclasses import dataclass
from typing import TypeVar

from utils import next_uid


@dataclass(init=False)
class UIDDataClass:
    id: int

    def __init__(self):
        self.id = next_uid()


ContainerObjectType = TypeVar("ContainerObjectType", bound=UIDDataClass)


class BaseContainer:
    _objects: dict[int, ContainerObjectType] = {}

    def __new__(cls, *args, **kwargs):
        raise TypeError("Non-instantiable class")

    @classmethod
    def add(cls, obj: ContainerObjectType) -> None:
        cls._objects[obj.id] = obj

    @classmethod
    def get(cls, obj: ContainerObjectType) -> ContainerObjectType:
        return cls._objects[obj.id]

    @classmethod
    def get_all(cls) -> dict[int, ContainerObjectType]:
        return cls._objects

    def __repr__(self) -> str:
        return f"{self.__name__!r}: {self._objects!r}"
