from __future__ import annotations

import logging
from datetime import datetime
from operator import attrgetter
from typing import TypeVar, Generic, TYPE_CHECKING, Type

from config import Config
from datastructures.rawtable.bbox import BBoxObject, BBox
from datastructures.rawtable.enums import RowType, ColumnType
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

    def __set_name__(self, owner, name):
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

    def _contains_time_data(self):
        """ Check if any field contains time data. """
        # TODO: Maybe add threshold as with sparsity?
        # TODO: Big problem when encountering dates ("nicht am 05.06")
        # TODO: Maybe add (bbox.x0 - table.bbox.x0) < X as a requirement?
        field_texts = [str(field.text).strip() for field in self.fields]
        for field_text in field_texts:
            try:
                datetime.strptime(field_text, Config.time_format)
                return True
            except ValueError:
                pass
        return False

    def __str__(self):
        return str([str(f) for f in self.fields])

    def __iter__(self):
        return self.fields.__iter__()

    def __repr__(self):
        name = self.__class__.__name__
        return f"{name}(fields: {str(self)}"


class Row(FieldContainer):
    # TODO: Instead of using enum for types use subclasses.
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

    def distance(self, other: Row, axis: str = "y") -> float:
        return self.bbox.distance(other.bbox, axis)

    def set_table(self, table: Table):
        self.table = table
        self.detect_type()

    @property
    def type(self):
        if not self._type:
            self.detect_type()
        return self._type

    def detect_type(self):
        # TODO: REDO.
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
        previous_row_is_annot = previous_row_is(RowType.ANNOTATION)
        if ((previous_row_is_header or previous_row_is_annot)
                and _contains(Config.annot_identifier)):
            self._type = RowType.ANNOTATION
            return
        self._type = RowType.OTHER

    def fits_column_scheme(self, columns: list[Column]):
        def get_stop_box():
            # Generate bbox for the stops, where we want to ignore the scheme.
            _bbox = None
            for _column in columns:
                if _column.type == ColumnType.DATA:
                    break
                if _bbox is None:
                    _bbox = _column.bbox.copy()
                    continue
                _bbox.merge(_column.bbox.copy())
            return _bbox

        def get_column_bbox() -> BBox:
            # Create new bbox, that spans between previous columns' end
            #  and next columns' start.
            _bbox = column.bbox.copy()
            if prev is not None:
                _bbox.x0 = min(_bbox.x0, prev.bbox.x1)
            if nxt is not None:
                _bbox.x0 = max(_bbox.x1, nxt.bbox.x0)
            return _bbox

        stop_bbox = get_stop_box()

        for field in self.fields:
            field_fits = False
            if stop_bbox and stop_bbox.contains_vertical(field.bbox):
                continue
            for prev, column, nxt in padded_list(columns):
                if column.type not in (ColumnType.DATA, ColumnType.REPEAT):
                    continue
                bbox = get_column_bbox()
                if bbox.contains_vertical(field.bbox):
                    field_fits = True
                    field.column = column
                    break
            # If a field does not fit, reset the column of the others as well.
            if not field_fits:
                for _field in self.fields:
                    _field.column = None
                return False

        # TODO: Check if message needs to be adjusted.
        logger.debug(f"Fields '{self.fields}' fit into column "
                     f"'{self.fields[0].column}'.")
        return True

    def apply_column_scheme(self, columns: list[Column | None]):
        def get_x_center(left: BBox, right: BBox) -> float:
            return round((right.x0 - left.x1) / 2, 2)

        unmatched_fields = sorted(self.fields, key=attrgetter("bbox.x0"))

        for prev_column, column, next_column in zip(*padded_list(columns)):
            # Get bbox where x-bounds are in the center between columns.
            bbox = column.bbox.copy()
            if prev_column is not None:
                bbox.x0 = bbox.x0 - get_x_center(prev_column.bbox, bbox)
            if next_column is not None:
                bbox.x1 = bbox.x1 + get_x_center(bbox, next_column.bbox)

            # Check if field fits stretched column bbox.
            for field in list(unmatched_fields):
                if not bbox.contains_vertical(field.bbox):
                    continue
                column.add_field(field)
                del unmatched_fields[unmatched_fields.index(field)]

    def __repr__(self):
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

    def _detect_type(self):
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
        else:
            self._type = ColumnType.DATA

    def _contains_repeat_identifier(self):
        # TODO: iterate through fields -> check for identifier
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

    def __repr__(self):
        fields_repr = ", ".join(repr(f) for f in self.fields)
        return f"Column(bbox={self.bbox},\n\tfields=[{fields_repr}])"

    @staticmethod
    def from_field(table, field):
        return Column(table, [field], field.bbox)
