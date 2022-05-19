from __future__ import annotations

from typing import TypeVar, Generic


FieldT = TypeVar("FieldT", bound="BaseField")
ContainerT = TypeVar("ContainerT", bound="BaseContainer")
TableTypeT = TypeVar("TableTypeT")
BaseContainerListT = TypeVar("BaseContainerListT", bound="BaseContainerList")


class BaseContainerReference(Generic[FieldT, ContainerT]):
    """ Descriptor for the row/column references of the fields. """

    def __set_name__(self, owner, name):
        self.public_name = name
        self.private_name = f"_{name}"
        setattr(owner, self.private_name, None)

    def __get__(self, obj: FieldT, objtype=None) -> ContainerT:
        return getattr(obj, self.private_name)

    def __set__(self, obj: FieldT, value: ContainerT) -> None:
        old_value: ContainerT = getattr(obj, self.private_name)
        if old_value:
            old_value.remove_field(obj)

        setattr(obj, self.private_name, value)


class BaseField:
    """ Baseclass for fields with a row and a column. """

    row = BaseContainerReference()
    column = BaseContainerReference()

    def __init__(self):
        self._row = None
        self._column = None


class BaseContainer(Generic[FieldT]):
    def __init__(self):
        self._fields: list[FieldT] = []
        self.field_attr = self.__class__.__name__.lower()

    @property
    def fields(self) -> list[FieldT]:
        return self._fields

    @fields.setter
    def fields(self, fields: list[FieldT]) -> None:
        for field in fields:
            self.add_reference_to_field(field)
        self._fields = fields

    def add_reference_to_field(self, field: FieldT) -> None:
        setattr(field, self.field_attr, self)

    def _add_field(self, new_field: FieldT, index: int):
        self.fields.insert(index, new_field)
        self.add_reference_to_field(new_field)

    def remove_field(self, field: FieldT) -> None:
        """ Remove the field from this container.

        Does not delete the field, only removes it from our fields.
        Will be called by the BaseContainerReference descriptor.
        """
        try:
            self.fields.remove(field)
        except ValueError:
            print("WARNING: "
                  "Tried to deregister field which was not in fields.")

    def __str__(self):
        return str([str(f) for f in self.fields])

    def __iter__(self):
        return self.fields.__iter__()


class BaseContainerList(Generic[TableTypeT, ContainerT]):
    def __init__(self, table: TableTypeT):
        self.objects: list[ContainerT] = []
        self.table = table

    def add(self, obj: ContainerT):
        self.objects.append(obj)
        self._update_reference(obj)

    def _update_reference(self, obj: ContainerT):
        obj.table = self.table

    def prev(self, current: ContainerT) -> ContainerT | None:
        return self._get_neighbour(current, -1)

    def next(self, current: ContainerT) -> ContainerT | None:
        return self._get_neighbour(current, 1)

    @classmethod
    def from_list(cls, table: TableTypeT, objects: list[ContainerT]
                  ) -> BaseContainerListT[TableTypeT, ContainerT]:
        instance = cls(table)
        for obj in objects:
            instance.add(obj)
        return instance

    def _get_neighbour(self, current: ContainerT, delta: int
                       ) -> ContainerT | None:
        neighbour_index = self.objects.index(current) + delta
        valid_index = 0 <= neighbour_index < len(self.objects)

        return self.objects[neighbour_index] if valid_index else None

    def __iter__(self):
        return iter(self.objects)
