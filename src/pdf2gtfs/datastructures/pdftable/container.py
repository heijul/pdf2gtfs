""" Containers i.e. Rows/Columns used by the PDFTable. """

from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from operator import attrgetter
from statistics import mean
from typing import Callable, Generic, Iterator, TYPE_CHECKING, TypeVar

from pdf2gtfs.config import Config
from pdf2gtfs.datastructures.pdftable.bbox import BBox, BBoxObject
from pdf2gtfs.datastructures.pdftable.enums import (
    ColumnType, FieldType, RowType)


if TYPE_CHECKING:
    from pdf2gtfs.datastructures.pdftable.pdftable import Cols, Rows, PDFTable
    from pdf2gtfs.datastructures.pdftable.field import Field

logger = logging.getLogger(__name__)

ContainerT = TypeVar("ContainerT", bound="FieldContainer")
TableT = TypeVar("TableT", bound="PDFTable")


class BaseContainerReference(Generic[ContainerT], ABC):
    """ Descriptor for the row/column references of the fields. """

    def __set_name__(self, owner, name) -> None:
        self.public_name = name
        self.private_name = f"_{name}"
        setattr(owner, self.private_name, None)

    def __get__(self, obj: Field, objtype=None) -> ContainerT:
        return getattr(obj, self.private_name)

    def __set__(self, obj: Field, value: ContainerT) -> None:
        old_value: FieldContainer = getattr(obj, self.private_name)
        if old_value:
            old_value.remove_field(obj)

        setattr(obj, self.private_name, value)


class FieldRowReference(BaseContainerReference["Row"]):
    """ Descriptor for the row reference of a field. """
    pass


class FieldColumnReference(BaseContainerReference["Column"]):
    """ Descriptor for the column reference of a field. """
    pass


class FieldContainer(BBoxObject):
    """ Base class for Row/Column. """

    def __init__(self, table: PDFTable = None, bbox: BBox = None):
        self._fields: list[Field] = []
        self.field_attr = self.__class__.__name__.lower()
        self._table = None
        BBoxObject.__init__(self, bbox)
        self.table = table
        self._type = None

    @property
    def fields(self) -> list[Field]:
        """ The fields within the FieldContainer. """
        return self._fields

    @fields.setter
    def fields(self, fields: list[Field]) -> None:
        for field in fields:
            self.add_reference_to_field(field)
        self._fields = fields
        self.set_bbox_from_fields()

    @property
    def table(self) -> TableT:
        """ The table the FieldContainer is part of. """
        return self._table

    @table.setter
    def table(self, table: TableT):
        self._table = table

    def has_type(self) -> bool:
        """ Whether the FieldContainer has any type. """
        return self._type is not None

    def add_reference_to_field(self, field: Field) -> None:
        """ Sets the reference set by self.field_attr of the field to self. """
        setattr(field, self.field_attr, self)

    def add_field(self, new_field: Field):
        """ Add new_field to our list of fields. """
        self._add_field_at_index(new_field, len(self.fields))

    def _add_field_at_index(self, new_field: Field, index: int):
        self.fields.insert(index, new_field)
        self.add_reference_to_field(new_field)

    def remove_field(self, field: Field) -> None:
        """ Remove the field from this container.

        Does not delete the field, only removes it from our fields.
        Will be called by the BaseContainerReference descriptor.
        """
        try:
            self.fields.remove(field)
        except ValueError:
            logger.debug(
                "Tried to deregister a field, which is not in fields.")

    def set_bbox_from_fields(self) -> None:
        """ Set the bbox such that it just contains all of our fields. """
        self._set_bbox_from_list(self.fields)

    def _add_field(self, new_field: Field, axis: str):
        index = 0
        lookup_field = f"{axis}0"
        for field in self.fields:
            field_lookup = getattr(field.bbox, lookup_field)
            new_field_lookup = getattr(new_field.bbox, lookup_field)
            if field_lookup >= new_field_lookup:
                break
            index += 1
        self._add_field_at_index(new_field, index)

    def _split_at(self, splitters: list[FieldContainer],
                  next_idx: Callable[[FieldContainer, Field], bool]
                  ) -> list[ContainerT]:
        """ Splits the container at splitters. next_idx should be a function,
        which takes the next available splitter and returns True,
        if the index should be incremented.
        """
        fields_list: list[list[Field]] = [[] for _ in splitters]
        splitters_iter = iter(splitters)
        current_splitter = next(splitters_iter)
        last_split = False
        idx = 0
        fields_copy = list(self.fields)
        current_field_id = 0
        while current_field_id < len(self.fields):
            field = fields_copy[current_field_id]
            if next_idx(current_splitter, field) and not last_split:
                try:
                    idx = splitters.index(current_splitter)
                    current_splitter = next(splitters_iter)
                except StopIteration:
                    last_split = True
                continue
            fields_list[idx].append(field)
            current_field_id += 1

        return [self.from_fields(fields) for fields in fields_list]

    def has_field_of_type(self, typ: FieldType) -> bool:
        """ Whether the FieldContainer contains a field with the given typ. """
        return any(map(lambda f: f.type == typ, self.fields))

    @staticmethod
    @abstractmethod
    def from_fields(fields: list[Field]) -> ContainerT:
        """ Create a new FieldContainer containing all fields. """
        pass

    def __str__(self) -> str:
        field_texts = " ".join([f.text for f in self.fields])
        return f"{str(self.__class__.__name__)}('{field_texts}')"

    def __iter__(self) -> Iterator[Field]:
        return self.fields.__iter__()

    def __repr__(self) -> str:
        name = self.__class__.__name__
        return f"{name}(fields: {str(self)}"


class Row(FieldContainer):
    """ A PDFTable row.
    The bboxes of all fields are overlapping horizontally. """

    def __init__(self, table: PDFTable = None, bbox: BBox = None):
        super().__init__(table, bbox)

    @staticmethod
    def from_fields(fields: list[Field]) -> Row:
        """ Creates a row containing all fields. """
        row = Row()
        row.fields = sorted(fields, key=attrgetter("bbox.x0"))
        row.set_bbox_from_fields()
        return row

    @property
    def index(self) -> int:
        """ Return the index of this row in the table. """
        return self.table.rows.index(self)

    def add_field(self, new_field: Field):
        """ Add new_field to our fields, maintaining proper order. """
        self._add_field(new_field, "x")

    def y_distance(self, other: Row) -> float:
        """ (y-) Distance between the two rows. """
        return self.bbox.y_distance(other.bbox)

    @property
    def type(self) -> RowType:
        """ The type of the Row. If the type is not set yet, set it first. """
        if not self._type:
            self.update_type()
        return self._type

    def update_type(self) -> None:
        """ Set the type. """
        self._type = self._detect_type()

    def _detect_type(self) -> RowType:
        if self.has_field_of_type(FieldType.HEADER):
            return RowType.HEADER
        if self.has_field_of_type(FieldType.ROW_ANNOT):
            return RowType.ANNOTATION
        if self.has_field_of_type(FieldType.ROUTE_INFO):
            return RowType.ROUTE_INFO
        if self.has_field_of_type(FieldType.DATA):
            return RowType.DATA
        return RowType.OTHER

    def split_at(self, splitter: Cols) -> Rows:
        """ Splits the row, depending on the given columns. """

        def _next_idx(column: FieldContainer, field: Field) -> bool:
            return column.bbox.x0 <= field.bbox.x0

        return self._split_at(splitter, _next_idx)

    def __repr__(self) -> str:
        fields_repr = ", ".join(repr(f) for f in self.fields)
        return (f"Row(type={self.type},\n\tbbox={self.bbox},\n\t"
                f"fields=[{fields_repr}])")


class Column(FieldContainer):
    """ A PDFTable column.
    The bboxes of all fields in the column are vertically overlapping. """

    def __init__(self, table: PDFTable = None,
                 fields: list[Field] = None,
                 bbox: BBox = None):
        super().__init__(table, bbox)
        self.fields: list[Field] = fields or []
        self.intervals = None

    @property
    def header_text(self) -> str:
        """ Return the header text of the column, if it exists or "". """
        return self.table.get_header_from_column(self)

    @property
    def type(self) -> ColumnType:
        """ The type of the column. If no type is set, it will be updated. """
        if not self._type:
            self._type = self._detect_type()
        return self._type

    @type.setter
    def type(self, value: ColumnType) -> None:
        self._type = value

    def _detect_type(self) -> ColumnType:
        def _constains_long_strings() -> bool:
            """ Returns if the column contains long strings. """
            return mean(map(lambda f: len(f.text), self.fields)) > 8

        def _is_sparse() -> bool:
            """ Returns if the column is sparse.

            Checks if more than 50% of fields of the column are empty.
            """
            empty_field_count = sum(map(lambda f: f.text == "", self.fields))
            # Use max() to prevent ZeroDivisionError.
            return (len(self.fields) / max(1, empty_field_count)) <= 0.5

        has_data_field = self.has_field_of_type(FieldType.DATA)

        if not _is_sparse() and _constains_long_strings():
            return ColumnType.STOP
        if self.has_repeat_interval():
            return ColumnType.REPEAT
        if self.has_field_of_type(FieldType.STOP_ANNOT):
            # Update previous column if current is a stop annotation and
            #  previous' type was not detected properly.
            previous = self.table.columns.prev(self)
            if previous.has_type() and previous.type == ColumnType.OTHER:
                previous.type = ColumnType.STOP
            return ColumnType.STOP_ANNOTATION
        if has_data_field:
            return ColumnType.DATA
        return ColumnType.OTHER

    def _get_repeat_intervals(self, start: str, end: str) -> list[str]:
        """ Finds all repeat intervals, if this is a repeat column. """
        start_regex = rf".*{re.escape(start)}\s*"
        value_regex = r"(\d{1,3}[-,]\ *\d{1,3}|\d{1,3})"
        end_regex = rf"\s*{re.escape(end)}.*"
        regex = start_regex + value_regex + end_regex

        texts = "\n".join([field.text for field in self.fields])
        matches = re.findall(regex, texts, flags=re.I + re.U)
        return matches

    def get_repeat_intervals(self) -> list[str]:
        """ Get all repeat intervals Try to find the start and end of the
        repeat_identifier in
        our fields. If both exist, try to get the repeat interval.
        """
        intervals = []
        for start, end in Config.repeat_identifier:
            intervals += self._get_repeat_intervals(start, end)
        return intervals

    def has_repeat_interval(self) -> bool:
        """ Check if the column contains at least one interval. """
        return bool(self.get_repeat_intervals())

    def merge(self, other: Column):
        """ Merge self with other, such that self contains all fields and its
        bbox contains all field bboxes. """
        for field in other.fields:
            self.add_field(field)
        self.set_bbox_from_fields()

    def add_field(self, new_field: Field):
        """ Add new_field, merging it with fields of the same row. """

        def _merge_into_fields() -> bool:
            """ If the field has the same row as an existing one merge them.
            :returns: True if the field was merged, False otherwise.
            """
            for field in self.fields:
                if field.row and field.row == new_field.row:
                    if (new_field.bbox.x0 - field.bbox.x1) != 0:
                        new_field.text = " " + new_field.text
                    field.merge(new_field)
                    return True
            return False

        if not _merge_into_fields():
            self._add_field(new_field, "y")
        self.set_bbox_from_fields()

    def __repr__(self) -> str:
        fields_repr = ", ".join(repr(f) for f in self.fields)
        return f"Column(bbox={self.bbox},\n\tfields=[{fields_repr}])"

    def split_at(self, splitter: Rows) -> Cols:
        """ Split the column at the given rows.

        Will return a list of columns, such that each column
        ,except the first, starts with a row from the given splitter.
        """

        def _next_idx(column: FieldContainer, field: Field) -> bool:
            return column.bbox.y0 <= field.bbox.y0

        return self._split_at(splitter, _next_idx)

    @staticmethod
    def from_field(table, field) -> Column:
        """ Creates a column from a single field. """
        return Column(table, [field], field.bbox)

    @staticmethod
    def from_fields(fields: list[Field]) -> Column:
        """ Creates a column from the given fields. """
        column = Column(fields=fields)
        column.set_bbox_from_fields()
        return column
