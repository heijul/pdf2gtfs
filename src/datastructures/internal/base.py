from __future__ import annotations

from typing import TypeVar, Generic, Type


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


class BaseContainer(Generic[FieldT, TableTypeT]):
    def __init__(self):
        self._fields: list[FieldT] = []
        self.field_attr = self.__class__.__name__.lower()
        self._table = None

    @property
    def fields(self) -> list[FieldT]:
        return self._fields

    @fields.setter
    def fields(self, fields: list[FieldT]) -> None:
        for field in fields:
            self.add_reference_to_field(field)
        self._fields = fields

    @property
    def table(self) -> Type[TableTypeT]:
        return self._table

    @table.setter
    def table(self, table: TableTypeT):
        self._table = table

    def add_reference_to_field(self, field: FieldT) -> None:
        setattr(field, self.field_attr, self)

    def add_field(self, new_field: FieldT):
        self._add_field(new_field, len(self.fields))

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

    def __repr__(self):
        name = self.__class__.__name__
        return f"{name}(fields: {str(self)}"


class BaseContainerList(Generic[TableTypeT, ContainerT]):
    def __init__(self, table: TableTypeT):
        self._objects: list[ContainerT] = []
        self.table = table

    def get_objects(self) -> list[ContainerT]:
        return self._objects

    def add(self, obj: ContainerT):
        self._objects.append(obj)
        self._update_reference(obj)

    def _update_reference(self, obj: ContainerT):
        obj.table = self.table

    def prev(self, current: ContainerT) -> ContainerT | None:
        return self._get_neighbour(current, -1)

    def next(self, current: ContainerT) -> ContainerT | None:
        return self._get_neighbour(current, 1)

    def index(self, obj: ContainerT) -> int:
        return self._objects.index(obj)

    @classmethod
    def from_list(cls, table: TableTypeT, objects: list[ContainerT]
                  ) -> BaseContainerListT[TableTypeT, ContainerT]:
        instance = cls(table)
        for obj in objects:
            instance.add(obj)
        return instance

    def _get_neighbour(self, current: ContainerT, delta: int
                       ) -> ContainerT | None:
        neighbour_index = self._objects.index(current) + delta
        valid_index = 0 <= neighbour_index < len(self._objects)

        return self._objects[neighbour_index] if valid_index else None

    def __iter__(self):
        return iter(self._objects)

    def __repr__(self):
        name = self.__class__.__name__
        obj_str = "\n\t".join([str(obj) for obj in self._objects])
        return f"{name}(\n\t{obj_str})"

    def __len__(self):
        return self._objects.__len__()
