""" Lists of containers (i.e. Row, Column) used by the PDFTable. """

from __future__ import annotations

from operator import attrgetter
from statistics import mean
from typing import Generic, Iterator, TypeVar

import datastructures.pdftable.pdftable as tbl
from datastructures.pdftable.container import Row, Column, FieldContainer
from datastructures.pdftable.enums import FieldContainerType


PDFTableT = TypeVar("PDFTableT", bound="tbl.PDFTable")
FieldContainerT = TypeVar("FieldContainerT", bound=FieldContainer)


class FieldContainerList(Generic[FieldContainerT]):
    """ Base class for lists of a single FieldContainerT,
    all being part of the same PDFTable. """
    def __init__(self, table: tbl.PDFTable):
        self._objects: list[FieldContainerT] = []
        self.table = table

    @property
    def objects(self) -> list[FieldContainerT]:
        """ The containers in this list. """
        return self._objects

    @property
    def empty(self) -> bool:
        """ Whether the list contains objects. """
        return len(self.objects) == 0

    def add(self, obj: FieldContainerT):
        """ Add the given object, updating its references. """
        self._objects.append(obj)
        self._update_reference(obj)

    def _update_reference(self, obj: FieldContainerT):
        obj.table = self.table

    def prev(self, current: FieldContainerT) -> FieldContainerT | None:
        """ Given the current container, return the previous one. """
        return self._get_neighbour(current, -1)

    def next(self, current: FieldContainerT) -> FieldContainerT | None:
        """ Given the current container, return the next one. """
        return self._get_neighbour(current, 1)

    def index(self, obj: FieldContainerT) -> int:
        """ Return the index of the given object. """
        return self._objects.index(obj)

    @classmethod
    def from_list(cls, table: tbl.PDFTable, objects: list[FieldContainerT]
                  ) -> FieldContainerList[FieldContainerT]:
        """ Create a new FieldContainerList,
        containing the given objects of the given table. """
        instance = cls(table)
        for obj in objects:
            instance.add(obj)
        return instance

    def of_type(self, typ: FieldContainerType) -> list[FieldContainerT]:
        """ Return all objects, which have the given typ. """
        return self.of_types([typ])

    def of_types(self, types: list[FieldContainerType]
                 ) -> list[FieldContainerT]:
        """ Return all objects, with any of the given types. """
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
        obj_str = "\n\t".join([str(obj) for obj in self.objects])
        return f"{name}(\n\t{obj_str})"

    def __len__(self) -> int:
        return len(self.objects)

    def __getitem__(self, item) -> FieldContainerT:
        return self.objects[item]


class ColumnList(FieldContainerList[Column]):
    """ List of columns. """
    pass


class RowList(FieldContainerList[Row]):
    """ List of rows. """
    def __init__(self, table: tbl.PDFTable):
        super().__init__(table)
        self._objects: list[Row] = []

    @property
    def mean_row_field_count(self) -> float:
        """ Return the average number of fields in all objects. """
        if not self._objects:
            return 0
        return mean([len(row.fields) for row in self._objects])

    def merge(self, other: RowList):
        """ Merge the two RowList, sorting the rows by their y0 coordinate. """
        self._objects += other.objects
        self._objects.sort(key=attrgetter("bbox.y0"))
