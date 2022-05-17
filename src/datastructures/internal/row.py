from __future__ import annotations

from datetime import datetime
from enum import Enum
from operator import attrgetter
from statistics import mean

import pandas as pd

from config import Config


class Bbox:
    def __init__(
            self, x0: float = 0, x1: float = 1, y0: float = 0, y1: float = 1):
        self.x0 = x0
        self.x1 = x1
        self.y0 = y0
        self.y1 = y1

    @property
    def size(self):
        return self.x1 - self.x0, self.y1 - self.y0

    @property
    def is_valid(self):
        return self.x0 < self.x1 and self.y0 < self.y1 and self.size > (0, 0)

    def _contains(self, other, axis):
        def _get(cls, bound):
            if bound == "lower":
                return getattr(cls, f"{axis}0")
            elif bound == "upper":
                return getattr(cls, f"{axis}1")

        lower, upper = _get(self, "lower"), _get(self, "upper")
        other_lower, other_upper = _get(other, "lower"), _get(other, "upper")

        return lower <= other_lower <= upper and lower <= other_upper <= upper

    def contains_vertical(self, other: Bbox):
        return self._contains(other, "x")

    def contains_horizontal(self, other: Bbox):
        return self._contains(other, "y")

    def contains(self, other: Bbox, strict: bool = False) -> bool:
        return (self.contains_vertical(other) and
                self.contains_horizontal(other) and
                (not strict or self.is_valid and other.is_valid))

    def merge(self, other: Bbox):
        self.x0 = min(self.x0, other.x0)
        self.x1 = max(self.x1, other.x1)
        self.y0 = min(self.y0, other.y0)
        self.y1 = max(self.y1, other.y1)

    def __repr__(self):
        return f"BBox(x0={self.x0}, x1={self.x1}, y0={self.y0}, y1={self.y1})"


class Field:
    def __init__(self, bbox: Bbox, text: str,
                 row: Row = None, column: Column = None):
        self.bbox = bbox
        self.text = text
        self.row = row
        self.column = column

    @staticmethod
    def from_char(char: pd.Series) -> Field:
        bbox = Bbox(char.x0, char.x1, char.y0, char.y1)
        return Field(bbox, char.text)

    def add_char(self, char: pd.Series) -> None:
        self.bbox.x1 = max(self.bbox.x1, char.x1)
        self.bbox.y0 = min(self.bbox.y0, char.y0)
        self.bbox.y1 = max(self.bbox.y1, char.y1)
        self.text += char.text

    def __str__(self):
        return str(self.text)

    def __repr__(self):
        return f"'{self.text}'"


class FieldContainer:
    def __init__(self, table: Table = None):
        self.table = table
        self._fields: list[Field] = []
        self.bbox = Bbox()
        self.field_attr = self.__class__.__name__.lower()

    @property
    def fields(self) -> list[Field]:
        return self._fields

    @fields.setter
    def fields(self, value: list[fields]) -> None:
        # Deregister row for old fields.
        for field in self._fields:
            setattr(field, self.field_attr, None)
        # Register row for new fields.
        for field in value:
            setattr(field, self.field_attr, self)

        self._fields = value

    def set_bbox(self, bbox: Bbox) -> None:
        self.bbox = bbox

    def set_bbox_from_fields(self) -> None:
        self.bbox = Bbox(min([f.bbox.x0 for f in self.fields], default=0),
                         max([f.bbox.x1 for f in self.fields], default=1),
                         min([f.bbox.y0 for f in self.fields], default=0),
                         max([f.bbox.y1 for f in self.fields], default=1))

    def merge_bbox(self, bbox: Bbox) -> None:
        # TODO: mb move to column
        self.bbox.merge(bbox)

    def _add_field(self, new_field: Field, axis: str):
        i = 0
        lookup_field = f"{axis}0"
        for field in self.fields:
            field_lookup = getattr(field.bbox, lookup_field)
            new_field_lookup = getattr(new_field.bbox, lookup_field)
            if field_lookup < new_field_lookup:
                break
            i += 1
        # TODO: Check if field.row/.column is updated.
        self.fields.insert(i, new_field)

    def _distance(self, other: FieldContainer, axis: str) -> float:
        # TODO: Move to bbox
        lower, upper = sorted([self, other], key=attrgetter(f"bbox.{axis}0"))
        if lower.bbox.x0 == upper.bbox.x0:
            return 0
        return (getattr(lower.bbox, f"{axis}1") -
                getattr(upper.bbox, f"{axis}0"))

    def __str__(self):
        return str([str(f) for f in self.fields])


class RowTypes(Enum):
    HEADER = 1
    DATA = 2
    OTHER = 3
    ANNOTATION = 4


class Row(FieldContainer):
    sparse: bool

    def __init__(self, table: Table = None):
        super().__init__(table)

        self._type = None

    @staticmethod
    def from_fields(fields: list[Field]) -> Row:
        row = Row()
        row.fields = fields
        row.set_bbox_from_fields()
        return row

    def add_field(self, new_field: Field):
        self._add_field(new_field, "x")

    def distance(self, other: Row) -> float:
        return self._distance(other, "y")

    def get_field_spans_x(self):
        return [(field.bbox.x0, field.bbox.x1) for field in self.fields]

    def set_table(self, table: Table):
        self.table = table
        self.detect_type()

    @property
    def sparse(self):
        # TODO: Add constant/config instead of magic number.
        return (len(self.fields) / self.table.mean_row_field_count) < 0.5

    @property
    def type(self):
        if not self._type:
            self.detect_type()
        return self._type

    @type.setter
    def type(self, value):
        # TODO: Maybe use Config.annotation_identifier instead of this!?
        if value != RowTypes.ANNOTATION:
            raise Exception(
                "Can not manually set another type than annotations.")
        self._type = RowTypes.ANNOTATION

    def detect_type(self):
        def _contains_header_identifier():
            """ Check if any of the fields contain a header identifier. """
            field_texts = [str(field.text).lower() for field in self.fields]
            return any([head in field_texts
                        for head in Config.header_identifier])

        def _contains_time_data():
            """ Check if any field contains time data. """
            # TODO: Maybe add threshold as with sparsity?
            # TODO: Big problem when encountering dates ("nicht am 05.06")
            # TODO: Maybe add (bbox.x0 - table.bbox.x0) < X as a requirement?
            field_texts = [str(field.text) for field in self.fields]
            for field_text in field_texts:
                try:
                    datetime.strptime(field_text, Config.time_format)
                    return True
                except ValueError:
                    pass
            return False

        # Once a row was recognized as annotation it stays an annotation.
        if self._type and self._type == RowTypes.ANNOTATION:
            self._type = RowTypes.ANNOTATION
            return
        if _contains_time_data():
            self._type = RowTypes.DATA
            return
        if _contains_header_identifier():
            self._type = RowTypes.HEADER
            return
        self._type = RowTypes.OTHER

    def fits_column_scheme(self, columns: list[Column]):
        for field in self.fields:
            field_fits = False
            # TODO: Instead of checking if column.bbox.contains, create
            #  new bbox with x0 = column[i].bbox.x0, x1 = column[i+1].bbox.x1
            for column in columns:
                if column.bbox.contains_vertical(field.bbox):
                    field_fits = True
                    break
            if not field_fits:
                return False
        return True

    def __repr__(self):
        fields_repr = ", ".join(repr(f) for f in self.fields)
        return (f"Row(type={self.type},\n\tbbox={self.bbox},\n\t"
                f"fields=[{fields_repr}])")


class Column(FieldContainer):
    def __init__(self, table: Table = None,
                 fields: list[Field] = None,
                 bbox: Bbox = Bbox()):
        super().__init__(table)
        self.fields = fields or []
        self.bbox = bbox

    @property
    def is_data_column(self):
        return ...

    def merge(self, other: Column):
        # Merge bbox.
        self.bbox.merge(other.bbox)
        # Merge fields.
        for field in other.fields:
            self.add_field(field)

    def add_field(self, new_field: Field):
        self._add_field(new_field, "y")

    def __repr__(self):
        fields_repr = ", ".join(repr(f) for f in self.fields)
        return f"Column(bbox={self.bbox},\n\tfields=[{fields_repr}])"

    @staticmethod
    def from_field(table, field):
        return Column(table, [field], field.bbox)


class RepeatColumn(Column):
    start_column: Column = None
    end_column: Column = None

    def __init__(self, table: Table = None):
        super().__init__(table)
        self.field_attr = "column"

    def expand(self) -> list[Column]:
        """ Expand the column into a list of columns. """
        ...


class Table:
    def __init__(self, rows: list[Row] = None, columns: list[Column] = None):
        self._set_rows(rows or [])
        self.columns = columns or []

    @property
    def rows(self):
        return self._rows

    @property
    def header_rows(self):
        return [row for row in self.rows if row.type == RowTypes.HEADER]

    def _set_rows(self, rows: list[Row]):
        self._rows = rows
        self.mean_row_field_count = mean([len(r.fields) for r in self._rows])
        # Needs to be done for all rows in case the mean has changed.
        for row in self._rows:
            row.set_table(self)

    def generate_data_columns_from_rows(self):
        def _get_bounds(_column: Column):
            return _column.bbox.x0, _column.bbox.x1

        def _column_x_is_overlapping(_c1: Column, field_column: Column):
            b1 = _get_bounds(_c1)
            b2 = _get_bounds(field_column)
            # Do not use equality here to prevent returning true
            #  for columns that are only touching.
            return b1[0] <= b2[0] <= b1[1] or b1[0] <= b2[1] <= b1[1]

        data_rows = [row for row in self.rows if row.type == RowTypes.DATA]
        if not data_rows:
            return

        # Generate single-field columns from the rows.
        field_columns = [Column.from_field(self, field)
                         for row in data_rows for field in row.fields]

        # Merge vertically overlapping columns.
        columns: list[Column] = []
        for column in sorted(field_columns, key=attrgetter("bbox.x0")):
            if not columns:
                columns.append(column)
                continue
            last = columns[-1]
            # Do not try to merge columns in the same row.
            if last.bbox.x1 <= column.bbox.x0:
                columns.append(column)
                continue
            if _column_x_is_overlapping(last, column):
                last.merge(column)

        # Try to fit the 'RowTypes.OTHER'-rows into the established data rows
        #  and update their type accordingly.
        for row in self.rows:
            if row.type != RowTypes.OTHER:
                continue
            if row.fits_column_scheme(columns):
                row.type = RowTypes.ANNOTATION

    @staticmethod
    def split_rows_into_tables(rows: list[Row]) -> list[Table]:
        tables = []
        current_rows = [rows[0]]

        for row in rows[1:]:
            distance_between_rows = abs(row.distance(current_rows[-1]))
            if distance_between_rows > Config.max_row_distance:
                print(f"Distance between rows: {distance_between_rows}")
                tables.append(Table(current_rows))
                current_rows = []
            current_rows.append(row)
        else:
            if current_rows:
                tables.append(Table(current_rows))
        return tables
