from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from datetime import datetime
from statistics import mean
from typing import Callable, Generic, Iterator, TYPE_CHECKING, TypeVar

from config import Config
from datastructures.rawtable.bbox import BBox, BBoxObject
from datastructures.rawtable.enums import ColumnType, FieldType, RowType


if TYPE_CHECKING:
    from datastructures.rawtable.table import Cols, Rows, Table
    from datastructures.rawtable.field import Field

logger = logging.getLogger(__name__)

ContainerT = TypeVar("ContainerT", bound="FieldContainer")
TableT = TypeVar("TableT", bound="Table")


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
    pass


class FieldColumnReference(BaseContainerReference["Column"]):
    pass


class FieldContainer(BBoxObject):
    """ Base class for Row/Column. """
    def __init__(self, table: Table = None, bbox: BBox = None):
        self._fields: list[Field] = []
        self.field_attr = self.__class__.__name__.lower()
        self._table = None
        BBoxObject.__init__(self, bbox)
        self.table = table
        self._type = None

    @property
    def fields(self) -> list[Field]:
        return self._fields

    @fields.setter
    def fields(self, fields: list[Field]) -> None:
        for field in fields:
            self.add_reference_to_field(field)
        self._fields = fields

    @property
    def table(self) -> TableT:
        return self._table

    @table.setter
    def table(self, table: TableT):
        self._table = table

    def has_type(self) -> bool:
        return self._type is not None

    def add_reference_to_field(self, field: Field) -> None:
        setattr(field, self.field_attr, self)

    def add_field(self, new_field: Field):
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

    def _contains_time_data(self) -> bool:
        """ Check if any field contains time data.

        This may rarely return True,
        e.g. if the field is an annotation with the text "nicht am 05.06.".
        """
        field_texts = [str(field.text).strip() for field in self.fields]
        for field_text in field_texts:
            try:
                datetime.strptime(field_text, Config.time_format)
                return True
            except ValueError:
                pass
        return False

    def _split_at(self, splitters: list[FieldContainer],
                  next_idx: Callable[[FieldContainer, Field], bool]
                  ) -> list[ContainerT]:
        """ Splits the container at splitters. next_idx should be a function,
        which takes the next available splitter and returns True,
        if the index should be incremented.
        """
        idx = 0
        fields_list: list[list[Field]] = [[] for _ in range(len(splitters))]

        for field in self.fields:
            splitter_available = idx + 1 < len(splitters)
            if splitter_available and next_idx(splitters[idx + 1], field):
                idx += 1
            fields_list[idx].append(field)
        return [self.from_fields(fields) for fields in fields_list]

    def has_field_of_type(self, typ: FieldType) -> bool:
        return any(map(lambda f: f.type == typ, self.fields))

    @staticmethod
    @abstractmethod
    def from_fields(fields: list[Field]) -> ContainerT:
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
    def __init__(self, table: Table = None, bbox: BBox = None):
        super().__init__(table, bbox)

    @staticmethod
    def from_fields(fields: list[Field]) -> Row:
        row = Row()
        row.fields = fields
        row.set_bbox_from_fields()
        return row

    def add_field(self, new_field: Field):
        self._add_field(new_field, "x")

    def y_distance(self, other: Row) -> float:
        return self.bbox.y_distance(other.bbox)

    @property
    def type(self) -> RowType:
        if not self._type:
            self.update_type()
        return self._type

    def update_type(self) -> None:
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
        def next_idx(column: FieldContainer, field: Field) -> bool:
            return column.bbox.x0 <= field.bbox.x0

        return self._split_at(splitter, next_idx)

    def __repr__(self) -> str:
        fields_repr = ", ".join(repr(f) for f in self.fields)
        return (f"Row(type={self.type},\n\tbbox={self.bbox},\n\t"
                f"fields=[{fields_repr}])")


class Column(FieldContainer):
    def __init__(self, table: Table = None,
                 fields: list[Field] = None,
                 bbox: BBox = None):
        super().__init__(table, bbox)
        self.fields: list[Field] = fields or []
        self.intervals = None

    @property
    def type(self) -> ColumnType:
        if not self._type:
            self.update_type()
        return self._type

    def set_to_stop(self) -> None:
        self._type = ColumnType.STOP

    def update_type(self) -> None:
        self._type = self._detect_type()

    def _detect_type(self) -> ColumnType:
        def _constains_long_strings() -> bool:
            """ Returns whether the average length of text is higher than 6. """
            return mean(map(lambda f: len(f.text), self.fields)) > 6

        def _is_not_sparse() -> bool:
            """ Returns whether the percentage of empty fields is less than 50%. """
            empty_field_count = sum(map(lambda f: f.text == "", self.fields))
            # Adding one to prevent ZeroDivisionError without changing result
            return ((1 + len(self.fields)) / (1 + empty_field_count)) > 0.5

        has_repeat_identifier = self.get_repeat_intervals() != ""
        has_data_field = self.has_field_of_type(FieldType.DATA)

        if _is_not_sparse() and _constains_long_strings():
            return ColumnType.STOP
        if has_repeat_identifier:
            return ColumnType.REPEAT
        if self.has_field_of_type(FieldType.STOP_ANNOT):
            # Update previous column if current is a stop annotation and
            #  previous' type was not detected properly.
            # CHECK: If this makes sense.
            previous = self.table.columns.prev(self)
            if previous.has_type() and previous.type == ColumnType.OTHER:
                previous.set_to_stop()
            return ColumnType.STOP_ANNOTATION
        if has_data_field:
            return ColumnType.DATA
        return ColumnType.OTHER

    def _get_repeat_interval_from_identifier(
            self, start_identifier: str, end_identifier: str) -> str:
        """ Returns the value between start_identifier and end_identifier. """
        start_regex = rf".*?{re.escape(start_identifier)}\s*"
        value_regex = r"(\d{1,3}[-,.]\d{1,3}|\d{1,3})"
        end_regex = rf"\s*{re.escape(end_identifier)}.*"
        regex = start_regex + value_regex + end_regex
        flags = re.IGNORECASE + re.UNICODE

        texts = "\n".join([field.text for field in self.fields])
        match = re.search(regex, texts, flags=flags)
        if not match:
            return ""
        return match.groups()[0]

    def get_repeat_intervals(self) -> str:
        if self.intervals is not None:
            return self.intervals
        for start, end in Config.repeat_identifier:
            interval = self._get_repeat_interval_from_identifier(start, end)
            if interval:
                self.intervals = interval
                return interval
        return ""

    def merge(self, other: Column):
        """ Merge self with other, such that self contains all fields and its
        bbox contains all field bboxes. """
        self.bbox.merge(other.bbox)
        for field in other.fields:
            self.add_field(field)

    def add_field(self, new_field: Field):
        def _merge_into_fields() -> bool:
            """ If the field has the same row as an existing one merge them.
            :returns: True if the field was merged, False otherwise.
            """
            for field in self.fields:
                if field.row == new_field.row:
                    if (new_field.bbox.x0 - field.bbox.x1) != 0:
                        new_field.text = " " + new_field.text
                    field.merge(new_field)
                    return True
            return False

        if _merge_into_fields():
            return
        self._add_field(new_field, "y")

    def __repr__(self) -> str:
        fields_repr = ", ".join(repr(f) for f in self.fields)
        return f"Column(bbox={self.bbox},\n\tfields=[{fields_repr}])"

    def split_at(self, splitter: Rows) -> Cols:
        def next_idx(column: FieldContainer, field: Field) -> bool:
            return column.bbox.y0 <= field.bbox.y0

        return self._split_at(splitter, next_idx)

    @staticmethod
    def from_field(table, field) -> Column:
        return Column(table, [field], field.bbox)

    @staticmethod
    def from_fields(fields: list[Field]) -> Column:
        column = Column(fields=fields)
        column.set_bbox_from_fields()
        return column
