from __future__ import annotations

import logging
import re
from datetime import datetime
from operator import attrgetter
from typing import Generic, Iterator, TYPE_CHECKING, TypeVar

from config import Config
from datastructures.rawtable.bbox import BBox, BBoxObject
from datastructures.rawtable.enums import ColumnType, RowType
from utils import padded_list


if TYPE_CHECKING:
    from datastructures.rawtable.table import Cols, Rows, Table
    from datastructures.rawtable.field import Field

logger = logging.getLogger(__name__)

ContainerT = TypeVar("ContainerT", bound="FieldContainer")
TableT = TypeVar("TableT", bound="Table")


class BaseContainerReference(Generic[ContainerT]):
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
    def __init__(self, table: Table = None, bbox: BBox = None):
        self._fields: list[Field] = []
        self.field_attr = self.__class__.__name__.lower()
        self._table = None
        BBoxObject.__init__(self, bbox)
        self.table = table

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

    def _contains_field_with_values(self, values: list[str]) -> bool:
        """ Check if any of the fields text match any of the values. """
        def _contains_field_with_value(value: str) -> bool:
            """ Returns true if value is equal to any field text. """
            return any([value.strip().lower() == field.text.strip().lower()
                        for field in self.fields])

        return any(_contains_field_with_value(value) for value in values)

    def _contains_time_data(self) -> bool:
        """ Check if any field contains time data. """
        # This may rarely return True, if field text contains the text "05.06"
        # of the annotation "nicht am 05.06.".
        field_texts = [str(field.text).strip() for field in self.fields]
        for field_text in field_texts:
            try:
                datetime.strptime(field_text, Config.time_format)
                return True
            except ValueError:
                pass
        return False

    def _split_at(self, splitter: Rows | Cols) -> list[ContainerT]:
        # Need copy, because of pop.
        splitter = list(splitter)
        fields_list: list[list[Field]] = [[]]
        for field in self.fields:
            if splitter and splitter[0].bbox.x0 <= field.bbox.x0:
                splitter.pop(0)
                fields_list.append([])
            fields_list[-1].append(field)
        return [self.from_fields(fields) for fields in fields_list if fields]

    @staticmethod
    def from_fields(fields: list[Field]) -> ContainerT:
        # TODO: Add abc
        pass

    def __str__(self) -> str:
        return str([str(f) for f in self.fields])

    def __iter__(self) -> Iterator[Field]:
        return self.fields.__iter__()

    def __repr__(self) -> str:
        name = self.__class__.__name__
        return f"{name}(fields: {str(self)}"


class Row(FieldContainer):
    def __init__(self, table: Table = None, bbox: BBox = None):
        super().__init__(table, bbox)
        self._type = None

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

    def set_table(self, table: Table):
        self.table = table
        self.update_type()

    @property
    def type(self) -> RowType:
        if not self._type:
            self.update_type()
        return self._type

    def update_type(self) -> None:
        self._type = self._detect_type()

    def _detect_type(self) -> RowType:
        # Once a row was recognized as annotation it stays an annotation.
        # CHECK: Why?
        if self._type and self._type == RowType.ANNOTATION:
            return RowType.ANNOTATION

        if self._contains_field_with_values(Config.header_values):
            return RowType.HEADER
        if self._contains_field_with_values(Config.annot_identifier):
            return RowType.ANNOTATION
        if self._contains_field_with_values(Config.route_identifier):
            return RowType.ROUTE_INFO
        if self._contains_time_data():
            return RowType.DATA
        return RowType.OTHER

    def apply_column_scheme(self, columns: list[Column | None]):
        # STYLE: This is actually three functions in a trenchcoat.
        from datastructures.rawtable.field import Field

        def get_stop_bbox() -> BBox:
            # Generate bbox for the stops, where we want to ignore the scheme.
            _bbox = None
            for _column in columns:
                if _column.type == ColumnType.DATA:
                    _bbox.x1 += get_x_center(_bbox, _column.bbox)
                    break
                if _bbox is None:
                    _bbox = _column.bbox.copy()
                    continue
                _bbox.merge(_column.bbox.copy())
            return _bbox

        def get_x_center(b1: BBox, b2: BBox) -> float:
            left, right = sorted([b1, b2], key=attrgetter("x0"))
            return round((right.x0 - left.x1) / 2, 2)

        def get_delta(_bbox: BBox, other_column: Column | None) -> float:
            if other_column is None:
                return 2
            return get_x_center(_bbox, other_column.bbox)

        stop_bbox = get_stop_bbox()
        fields = [field for field in self.fields
                  if not stop_bbox.contains_vertical(field.bbox)]
        unmatched_fields = sorted(fields, key=attrgetter("bbox.x0"))
        column_matches: dict[Column: list[Field]] = {}

        for prev_column, column, next_column in zip(*padded_list(columns)):
            if stop_bbox.contains_vertical(column.bbox):
                continue
            # Get bbox where x-bounds are in the center between columns.
            bbox = column.bbox.copy()
            bbox.x0 -= get_delta(bbox, prev_column)
            bbox.x1 += get_delta(bbox, next_column)

            column_matches[column] = []
            # Check if field fits stretched column bbox.
            for field in list(unmatched_fields):
                if not bbox.contains_vertical(field.bbox):
                    continue
                column_matches[column].append(field)
                del unmatched_fields[unmatched_fields.index(field)]

        # Only apply the column scheme, if all fields fit (except stopcolumn).
        if unmatched_fields:
            fields = "\n\t".join(map(str, unmatched_fields))
            logger.debug("Tried to apply column scheme, but could not match "
                         f"the following fields:\n\t{fields}")
            return

        for column, fields in column_matches.items():
            # Add empty field, to ensure all columns have the same height.
            if not fields:
                bbox = BBox(column.bbox.x0, self.bbox.y0,
                            column.bbox.x1, self.bbox.y1)
                field = Field(bbox, "")
                self.add_field(field)
                fields = [field]
            for field in fields:
                column.add_field(field)

    def split_at(self, columns: list[Column]) -> list[Row]:
        """ Splits the row, depending on the given columns. """
        return self._split_at(columns)

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
        self._type = None
        self.intervals = None

    @property
    def type(self) -> ColumnType:
        if not self._type:
            self.update_type()
        return self._type

    def update_type(self) -> None:
        self._type = self._detect_type()

    def _detect_type(self) -> ColumnType:
        previous = self.table.columns.prev(self)

        # CHECK: First column is always a stop?
        if not previous:
            return ColumnType.STOP

        has_time_data = self._contains_time_data()
        has_repeat_identifier = self.get_repeat_intervals() != ""

        if has_repeat_identifier:
            return ColumnType.REPEAT
        if not has_time_data and previous.type == ColumnType.STOP:
            return ColumnType.STOP_ANNOTATION
        if not has_time_data and not has_repeat_identifier:
            return ColumnType.STOP
        return ColumnType.DATA

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
        return self._split_at(splitter)

    @staticmethod
    def from_field(table, field) -> Column:
        return Column(table, [field], field.bbox)

    @staticmethod
    def from_fields(fields: list[Field]) -> Column:
        column = Column(fields=fields)
        column.set_bbox_from_fields()
        return column
