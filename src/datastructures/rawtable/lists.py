from __future__ import annotations

from operator import attrgetter
from statistics import mean
from typing import Generic, Iterator, TypeVar

import datastructures.rawtable.table as tbl
from datastructures.rawtable.container import Row, Column
from datastructures.rawtable.enums import FieldContainerType


FieldContainerT = TypeVar("FieldContainerT", bound="FieldContainer")
TableT = TypeVar("TableT", bound="Table")


class FieldContainerList(Generic[TableT, FieldContainerT]):
    def __init__(self, table: TableT):
        self._objects: list[FieldContainerT] = []
        self.table = table

    def get_objects(self) -> list[FieldContainerT]:
        return self._objects

    def add(self, obj: FieldContainerT):
        self._objects.append(obj)
        self._update_reference(obj)

    def _update_reference(self, obj: FieldContainerT):
        obj.table = self.table

    def prev(self, current: FieldContainerT) -> FieldContainerT | None:
        return self._get_neighbour(current, -1)

    def next(self, current: FieldContainerT) -> FieldContainerT | None:
        return self._get_neighbour(current, 1)

    def index(self, obj: FieldContainerT) -> int:
        return self._objects.index(obj)

    @classmethod
    def from_list(cls, table: TableT, objects: list[FieldContainerT]
                  ) -> FieldContainerList[TableT, FieldContainerT]:
        instance = cls(table)
        for obj in objects:
            instance.add(obj)
        return instance

    def of_type(self, typ: FieldContainerType) -> list[FieldContainerT]:
        return self.of_types([typ])

    def of_types(self, types: list[FieldContainerType]
                 ) -> list[FieldContainerT]:
        return [obj for obj in self._objects if obj.type in types]

    def _get_neighbour(self, current: FieldContainerT, delta: int
                       ) -> FieldContainerT | None:
        neighbour_index = self._objects.index(current) + delta
        valid_index = 0 <= neighbour_index < len(self._objects)

        return self._objects[neighbour_index] if valid_index else None

    def __iter__(self) -> Iterator[FieldContainerT]:
        return iter(self._objects)

    def __repr__(self) -> str:
        name = self.__class__.__name__
        obj_str = "\n\t".join([str(obj) for obj in self._objects])
        return f"{name}(\n\t{obj_str})"

    def __len__(self) -> int:
        return self._objects.__len__()


class ColumnList(FieldContainerList[TableT, Column]):
    pass


class RowList(FieldContainerList[TableT, Row]):
    def __init__(self, table: tbl.Table):
        super().__init__(table)
        self._objects: list[Row] = []

    @property
    def mean_row_field_count(self) -> float:
        if not self._objects:
            return 0
        return mean([len(row.fields) for row in self._objects])

    def merge(self, other: RowList):
        self._objects += other.get_objects()
        self._objects.sort(key=attrgetter("bbox.y0"))
