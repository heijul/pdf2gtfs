from __future__ import annotations

from datetime import datetime
from operator import attrgetter
from typing import TypeVar, Generic, TYPE_CHECKING, Type

from config import Config
from datastructures.rawtable.bbox import BBoxObject, BBox


if TYPE_CHECKING:
    from datastructures.rawtable.table import Table
    from datastructures.rawtable.fields import Field

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
            print("WARNING: Tried to deregister field which is not in fields.")

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
    def from_fields(fields: list[Field]) -> RowT:
        def _contains(idents: list[str]):
            """ Check if any of the fields contain any of the identifier. """
            return any([ident.strip().lower() in field_texts
                        for ident in idents])

        def _contains_time_data():
            """ Check if any field contains time data. """
            # TODO: Maybe add threshold as with sparsity?
            # TODO: Big problem when encountering dates ("nicht am 05.06")
            # TODO: Maybe add (bbox.x0 - table.bbox.x0) < X as a requirement?
            for field_text in field_texts:
                try:
                    datetime.strptime(field_text, Config.time_format)
                    return True
                except ValueError:
                    pass
            return False

        def get_row_class():
            if _contains(Config.header_values):
                return HeaderRow
            if _contains(Config.annot_identifier):
                return AnnotationRow
            if _contains(Config.route_identifier):
                return RouteRow
            if _contains_time_data():
                return DataRow
            return Row

        field_texts = [str(field.text).strip().lower() for field in fields]
        row = get_row_class()()
        row.fields = fields
        row.set_bbox_from_fields()
        return row

    def add_field(self, new_field: Field):
        self._add_field(new_field, "x")

    def distance(self, other: Row, axis: str = "y") -> float:
        return self.bbox.distance(other.bbox, axis)

    def set_table(self, table: Table):
        self.table = table

    def fits_column_scheme(self, columns: list[Column]):
        # Generate bbox for the stops, where we want to ignore the scheme.
        stop_bbox = None
        for column in columns:
            if isinstance(column, DataColumn):
                break
            if stop_bbox is None:
                stop_bbox = column.bbox.copy()
                continue
            stop_bbox.merge(column.bbox.copy())

        for field in self.fields:
            field_fits = False
            if stop_bbox and stop_bbox.contains_vertical(field.bbox):
                continue
            # TODO: Instead of checking if column.bbox.contains, create
            #  new bbox with x0 = column[i].bbox.x0, x1 = column[i+1].bbox.x1
            for column in columns:
                if isinstance(column, (DataColumn, RepeatColumn)):
                    continue
                if column.bbox.contains_vertical(field.bbox):
                    field_fits = True
                    field.column = column
                    break
            if not field_fits:
                for _field in self.fields:
                    _field.column = None
                return False
        return True

    def apply_column_scheme(self, columns: list[Column]):
        unmatched_fields = sorted(self.fields, key=attrgetter("bbox.x0"))
        for column in columns:
            for field in list(unmatched_fields):
                if not column.bbox.contains_vertical(field.bbox):
                    continue
                column.add_field(field)
                del unmatched_fields[unmatched_fields.index(field)]

    def __repr__(self):
        fields_repr = ", ".join(repr(f) for f in self.fields)
        return (f"Row(type={self.__class__},\n\tbbox={self.bbox},\n\t"
                f"fields=[{fields_repr}])")


class HeaderRow(Row):
    pass


class DataRow(Row):
    pass


class AnnotationRow(Row):
    pass


class RouteRow(Row):
    def routes(self):
        """ Return set of all routes. """
        routes = [field.text.strip() for field in self.fields
                  if field not in Config.route_identifier]
        return set(routes)


class Column(FieldContainer):
    def __init__(self, table: Table = None,
                 fields: list[Field] = None,
                 bbox: BBox = None):
        super().__init__(table, bbox)
        self.fields: list[Field] = fields or []

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
        # TODO: Maybe do in one loop in _add_field instead of two.
        for field in self.fields:
            if field.row == new_field.row:
                new_field.text = " " + new_field.text
                field.merge(new_field)
                return
        self._add_field(new_field, "y")

    def __repr__(self):
        fields_repr = ", ".join(repr(f) for f in self.fields)
        return f"Column(bbox={self.bbox},\n\tfields=[{fields_repr}])"

    @staticmethod
    def from_field(table, field):
        return Column(table, [field], field.bbox)


class StopColumn(Column):
    pass


class AnnotationColumn(Column):
    pass


class DataColumn(Column):
    pass


class RepeatColumn(Column):
    pass
