from __future__ import annotations

import logging
from datetime import datetime
from operator import attrgetter
from typing import Generic, Iterator, Type, TYPE_CHECKING, TypeVar

from config import Config
from datastructures.rawtable.bbox import BBox, BBoxObject
from datastructures.rawtable.enums import ColumnType, RowType
from utils import padded_list


if TYPE_CHECKING:
    from datastructures.rawtable.table import Table
    from datastructures.rawtable.fields import Field


logger = logging.getLogger(__name__)

RowT = TypeVar("RowT", bound="Row")
ColumnT = TypeVar("ColumnT", bound="Column")
ContainerT = TypeVar("ContainerT", bound="BaseContainer")
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


class FieldRowReference(BaseContainerReference[RowT]):
    pass


class FieldColumnReference(BaseContainerReference[ColumnT]):
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
    def table(self) -> Type[TableT]:
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
        self.detect_type()

    @property
    def type(self) -> RowType:
        if not self._type:
            self.detect_type()
        return self._type

    def detect_type(self) -> None:
        # IMPROVE: REDO.
        def _contains(idents: list[str]):
            """ Check if any of the fields contain any of the identifier. """
            field_texts = [str(field.text).lower() for field in self.fields]
            return any([ident.strip().lower() in field_texts
                        for ident in idents])

        def previous_row_is(_type: RowType):
            try:
                previous = self.table.rows.prev(self)
            except AttributeError:
                # No table set yet
                return False
            if not previous:
                return True
            return previous.type == _type

        # Once a row was recognized as annotation it stays an annotation.
        if self._type and self._type == RowType.ANNOTATION:
            return
        if self._contains_time_data():
            self._type = RowType.DATA
            return
        previous_row_is_header = previous_row_is(RowType.HEADER)
        if previous_row_is_header and _contains(Config.header_values):
            self._type = RowType.HEADER
            return
        elif _contains(Config.annot_identifier):
            self._type = RowType.ANNOTATION
        elif _contains(Config.route_identifier):
            self._type = RowType.ROUTE_INFO
        else:
            self._type = RowType.OTHER

    def apply_column_scheme(self, columns: list[Column | None]):
        # STYLE: This is actually three functions in a trenchcoat.
        from datastructures.rawtable.fields import Field

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
        fields_list: list[list[Field]] = [[]]
        columns = list(columns[1:])

        for field in self.fields:
            if columns and columns[0].bbox.x0 <= field.bbox.x0:
                columns.pop(0)
                fields_list.append([])
            fields_list[-1].append(field)

        return [Row.from_fields(fields) for fields in fields_list]

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

    @property
    def type(self) -> ColumnType:
        if not hasattr(self, "_type"):
            self._detect_type()
        return self._type

    def _detect_type(self) -> None:
        previous = self.table.columns.prev(self)

        if not previous:
            self._type = ColumnType.STOP
            return

        has_time_data = self._contains_time_data()
        has_repeat_identifier = self._contains_repeat_identifier()

        if has_repeat_identifier:
            self._type = ColumnType.REPEAT
        elif previous.type == ColumnType.STOP and not has_time_data:
            self._type = ColumnType.STOP_ANNOTATION
        elif not has_time_data and not has_repeat_identifier:
            self._type = ColumnType.STOP
        else:
            self._type = ColumnType.DATA

    def _contains_repeat_identifier(self) -> bool:
        # IMPROVE: iterate through fields -> check for identifier
        #  -> check for num -> (maybe check for min/min.)
        return any([f.text.lower() in Config.repeat_identifier
                    for f in self.fields])

    def merge(self, other: Column):
        # Merge bbox.
        self.bbox.merge(other.bbox)
        # Merge fields.
        for field in other.fields:
            self.add_field(field)

    def add_field(self, new_field: Field):
        if self.merge_into_fields(new_field):
            return
        self._add_field(new_field, "y")

    def merge_into_fields(self, new_field: Field) -> bool:
        """ If the field has the same row as an existing one merge them.
        :returns: True if the field was merged, False otherwise.
        """
        for field in self.fields:
            if field.row == new_field.row:
                new_field.text = " " + new_field.text
                field.merge(new_field)
                return True
        return False

    def __repr__(self) -> str:
        fields_repr = ", ".join(repr(f) for f in self.fields)
        return f"Column(bbox={self.bbox},\n\tfields=[{fields_repr}])"

    @staticmethod
    def from_field(table, field) -> Column:
        return Column(table, [field], field.bbox)
