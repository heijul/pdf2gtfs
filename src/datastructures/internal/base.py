from __future__ import annotations

from typing import TypeVar, Type


class BaseContainer:
    def __init__(self):
        self._fields: list[BaseFieldT] = []
        self.field_attr = self.__class__.__name__.lower()

    @property
    def fields(self) -> list[BaseFieldT]:
        return self._fields

    @fields.setter
    def fields(self, value: list[BaseFieldT]) -> None:
        for field in self._fields:
            field.register(self.field_attr, self)

        self._fields = value

    def deregister_field(self, field):
        try:
            self.fields.remove(field)
        except ValueError:
            print("WARNING: "
                  "Tried to deregister field which was not in fields.")

    def _add_field(self, new_field: BaseFieldT, index: int):
        self.fields.insert(index, new_field)
        new_field.register(self.field_attr, self)

    def __str__(self):
        return str([str(f) for f in self.fields])

    def __iter__(self):
        return self.fields.__iter__()


class BaseField:
    """ BaseField which exists inside one or more containers. """

    def __init__(self, containers: dict[str, Type[BaseContainerT]]):
        self.containers = containers
        for attr in self.containers:
            setattr(self, attr, None)

    def register(self, attr: str, to: BaseContainerT):
        if attr not in self.containers:
            raise Exception(
                f"Attribute {attr} not in attr_list {self.containers}.")
        if to and not isinstance(to, self.containers.get(attr)):
            raise Exception(f"Invalid attribute type. Expected "
                            f"'{self.containers[attr]}', got '{type(to)}'")

        self.deregister(attr)
        setattr(self, attr, to)

    def deregister(self, attr_name: str):
        if attr_name not in self.containers:
            raise Exception(
                f"Attribute {attr_name} not in attr_list {self.containers}.")

        attr_value = getattr(self, attr_name)
        if attr_value:
            attr_value.deregister_field(self)
        setattr(self, attr_name, None)


BaseContainerT = TypeVar("BaseContainerT", bound="BaseContainer")
BaseFieldT = TypeVar("BaseFieldT", bound="BaseField")

