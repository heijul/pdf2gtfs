from __future__ import annotations

from datetime import datetime
from enum import Enum
from operator import attrgetter
from statistics import mean
from typing import TypeVar, TYPE_CHECKING, Generic

import pandas as pd

from config import Config
from datastructures.internal.base import (
    BaseField, BaseContainer, BaseContainerReference, BaseContainerList)


if TYPE_CHECKING:
    from datastructures.internal.timetable import TimeTable


FieldT = TypeVar("FieldT", bound="Field")
RowT = TypeVar("RowT", bound="Row")
ColumnT = TypeVar("ColumnT", bound="Column")
FieldContainerT = TypeVar("FieldContainerT", bound="FieldContainer")
TableT = TypeVar("TableT", bound="Table")


# TODO: Maybe change to 'proper bbox' (x0, y0, x1, y1).
class BBox:
    """ Bounding box. Represented as (x0, x1, y0, y1). """
    def __init__(
            self, x0: float = 0, x1: float = 1, y0: float = 0, y1: float = 1):
        self.x0 = x0
        self.x1 = x1
        self.y0 = y0
        self.y1 = y1

    @staticmethod
    def from_series(series: pd.Series):
        return BBox(series.x0, series.x1, series.y0, series.y1)

    @property
    def size(self):
        return self.x1 - self.x0, self.y1 - self.y0

    @property
    def is_valid(self):
        return self.x0 < self.x1 and self.y0 < self.y1 and self.size > (0, 0)

    def copy(self) -> BBox:
        return BBox(self.x0, self.x1, self.y0, self.y1)

    def contains_vertical(self, other: BBox):
        return self._contains(other, "x")

    def contains_horizontal(self, other: BBox):
        return self._contains(other, "y")

    def contains(self, other: BBox, strict: bool = False) -> bool:
        return (self.contains_vertical(other) and
                self.contains_horizontal(other) and
                (not strict or self.is_valid and other.is_valid))

    def merge(self, other: BBox) -> None:
        self.x0 = min(self.x0, other.x0)
        self.x1 = max(self.x1, other.x1)
        self.y0 = min(self.y0, other.y0)
        self.y1 = max(self.y1, other.y1)

    def set(self, coordinate: str, value: float) -> None:
        assert coordinate in ["x0", "x1", "y0", "y1"]
        setattr(self, coordinate, value)

    def _contains(self, other, axis):
        def _get(cls, bound):
            if bound == "lower":
                return getattr(cls, f"{axis}0")
            elif bound == "upper":
                return getattr(cls, f"{axis}1")

        lower, upper = _get(self, "lower"), _get(self, "upper")
        other_lower, other_upper = _get(other, "lower"), _get(other, "upper")

        return lower <= other_lower <= upper and lower <= other_upper <= upper

    def __repr__(self):
        return f"BBox(x0={self.x0}, x1={self.x1}, y0={self.y0}, y1={self.y1})"


class BBoxObject:
    """ Baseclass for objects which have a bbox. """

    def __init__(self, bbox: BBox | None = None) -> None:
        self._set_bbox(bbox)

    def merge(self, other: BBoxObject | BBox):
        other_bbox = other if isinstance(other, BBox) else other.bbox
        self.bbox.x0 = min(self.bbox.x0, other_bbox.x0)
        self.bbox.x1 = max(self.bbox.x1, other_bbox.x1)
        self.bbox.y0 = min(self.bbox.y0, other_bbox.y0)
        self.bbox.y1 = max(self.bbox.y1, other_bbox.y1)

    def _set_bbox(self, bbox: BBox | None) -> None:
        self.bbox = BBox() if bbox is None else bbox

    def _distance(self, other: FieldContainer, axis: str) -> float:
        # TODO: Move to bbox
        lower, upper = sorted([self, other], key=attrgetter(f"bbox.{axis}0"))
        lower_0 = getattr(lower.bbox, f"{axis}0")
        lower_1 = getattr(lower.bbox, f"{axis}1")
        upper_0 = getattr(upper.bbox, f"{axis}0")
        upper_1 = getattr(upper.bbox, f"{axis}1")
        return min([abs(lower_0 - upper_0),
                    abs(lower_1 - upper_0),
                    abs(lower_1 - upper_1)])

    def _set_bbox_from_list(self, bbobjects: list[BBoxObject]):
        # TODO: Check default.
        if not bbobjects:
            self._set_bbox(None)
            return
        bbox = bbobjects[0].bbox.copy()
        for obj in bbobjects[1:]:
            bbox.merge(obj.bbox)

        self._set_bbox(bbox)


class FieldRowReference(BaseContainerReference[FieldT, RowT]):
    pass


class FieldColumnReference(BaseContainerReference[FieldT, ColumnT]):
    pass


class Field(BaseField, BBoxObject):
    row: Row = FieldRowReference()
    column: Column = FieldColumnReference()

    def __init__(self, bbox: BBox, text: str):
        BaseField.__init__(self)
        BBoxObject.__init__(self, bbox)
        self.text = text

    @staticmethod
    def from_char(char: pd.Series) -> Field:
        return Field(BBox.from_series(char), char.text)

    def add_char(self, char: pd.Series) -> None:
        super().merge(BBox.from_series(char))
        self.text += char.text

    def merge(self, other: Field):
        super().merge(other.bbox)
        self.text += other.text

    def __str__(self):
        return str(self.text)

    def __repr__(self):
        return f"'{self.text}'"


class FieldContainerType(Enum):
    pass


class RowType(FieldContainerType):
    HEADER = 1
    DATA = 2
    OTHER = 3
    ANNOTATION = 4


class ColumnType(FieldContainerType):
    STOP = 1
    STOP_ANNOTATION = 2
    DATA = 3


class FieldContainer(BaseContainer[Field, TableT], BBoxObject):
    def __init__(self, table: Table = None, bbox: BBox = None):
        BaseContainer.__init__(self)
        BBoxObject.__init__(self, bbox)
        self.table = table

    def set_bbox_from_fields(self) -> None:
        self._set_bbox_from_list(self.fields)

    def _add_field(self, new_field: Field, axis: str):
        index = 0
        lookup_field = f"{axis}0"
        for field in self.fields:
            field_lookup = getattr(field.bbox, lookup_field)
            new_field_lookup = getattr(new_field.bbox, lookup_field)
            if field_lookup < new_field_lookup:
                break
            index += 1
        super()._add_field_at_index(new_field, index)

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
        return self._distance(other, axis)

    def set_table(self, table: Table):
        self.table = table
        self.detect_type()

    @property
    def type(self):
        if not self._type:
            self.detect_type()
        return self._type

    @type.setter
    def type(self, value):
        if value != RowType.ANNOTATION:
            raise Exception(
                "Can not manually set another type than annotations.")
        self._type = RowType.ANNOTATION

    def detect_type(self):
        def _contains_header_identifier():
            """ Check if any of the fields contain a header identifier. """
            field_texts = [str(field.text).lower() for field in self.fields]
            return any([head in field_texts
                        for head in Config.header_identifier])

        def previous_row_is_header():
            try:
                previous = self.table.rows.prev(self)
            except AttributeError:
                # No table set yet -> no header
                return False
            if not previous:
                return True
            return previous.type == RowType.HEADER

        # Once a row was recognized as annotation it stays an annotation.
        if self._type and self._type == RowType.ANNOTATION:
            return
        if self._contains_time_data():
            self._type = RowType.DATA
            return
        if previous_row_is_header() and _contains_header_identifier():
            self._type = RowType.HEADER
            return
        self._type = RowType.OTHER

    def fits_column_scheme(self, columns: list[Column]):
        # Generate bbox for the stops, where we want to ignore the scheme.
        stop_bbox = None
        for column in columns:
            if column.type == ColumnType.DATA:
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
                if column.type != ColumnType.DATA:
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
        if previous.type == ColumnType.STOP and not has_time_data:
            self._type = ColumnType.STOP_ANNOTATION
        else:
            self._type = ColumnType.DATA

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


class FieldContainerList(Generic[TableT, FieldContainerT],
                         BaseContainerList[TableT, FieldContainerT]):
    def of_type(self, typ: FieldContainerType) -> list[FieldContainerT]:
        return [obj for obj in self._objects if obj.type == typ]


class ColumnList(FieldContainerList[TableT, Column]):
    pass


class RowList(FieldContainerList[TableT, Row]):
    def __init__(self, table: Table):
        super().__init__(table)
        self._objects: list[Row] = []

    @property
    def mean_row_field_count(self):
        if not self._objects:
            return 0
        return mean([len(row.fields) for row in self._objects])


class Table:
    def __init__(self, rows: list[Row] = None, columns: list[Column] = None):
        self.rows = rows or []
        self.columns = columns or []

    @property
    def rows(self) -> RowList:
        return self._rows

    @rows.setter
    def rows(self, rows: list[Row] | RowList) -> None:
        if isinstance(rows, RowList):
            self._rows = rows
        else:
            self._rows = RowList.from_list(self, rows)

    @property
    def columns(self) -> ColumnList:
        return self._columns

    @columns.setter
    def columns(self, columns: list[Column] | ColumnList):
        if isinstance(columns, ColumnList):
            self._columns = columns
        else:
            self._columns = ColumnList.from_list(self, columns)

    @property
    def header_rows(self):
        return self.rows.of_type(RowType.HEADER)

    def generate_data_columns_from_rows(self):
        def _get_bounds(_column: Column):
            return _column.bbox.x0, _column.bbox.x1

        def _column_x_is_overlapping(_c1: Column, field_column: Column):
            b1 = _get_bounds(_c1)
            b2 = _get_bounds(field_column)
            # Do not use equality here to prevent returning true
            #  for columns that are only touching.
            return b1[0] <= b2[0] <= b1[1] or b1[0] <= b2[1] <= b1[1]

        data_rows = self.rows.of_type(RowType.DATA)
        if not data_rows:
            return

        # Generate single-field columns from the rows.
        field_columns = [Column.from_field(self, field)
                         for row in data_rows for field in row]

        # Merge vertically overlapping columns.
        columns: list[Column] = []
        for column in sorted(field_columns, key=attrgetter("bbox.x0")):
            if not columns:
                columns.append(Column.from_field(self, column.fields[0]))
                continue
            last = columns[-1]
            # Do not try to merge columns in the same row.
            if last.bbox.x1 <= column.bbox.x0:
                columns.append(Column.from_field(self, column.fields[0]))
                continue
            if _column_x_is_overlapping(last, column):
                last.add_field(column.fields[0])

        # Expand columns so their x-bounds are in the center between columns.
        last = columns[0] if len(columns) else None
        dist = 0
        for column in columns[1:]:
            dist = column.bbox.x0 - last.bbox.x1
            new_bound = round(last.bbox.x1 + dist / 2, 2)

            last.bbox.set("x1", new_bound)
            column.bbox.set("x0", new_bound)
            last = column
        last.bbox.set("x1", round(last.bbox.x1 + dist / 2, 2))

        self.columns = columns

        # Try to fit the 'RowTypes.OTHER'-rows into the established data rows
        #  and update their type accordingly.
        # TODO: Maybe use Config.annotation_identifier instead of this!?
        for row in self.rows:
            if row.type != RowType.OTHER:
                continue
            if row.fits_column_scheme(columns):
                row.type = RowType.ANNOTATION

    @staticmethod
    def split_rows_into_tables(rows: list[Row]) -> list[Table]:
        tables = []
        current_rows = [rows[0]]
        min_row_count = 3
        for row in rows[1:]:
            if not row.fields:
                continue
            y_distance = abs(row.distance(current_rows[-1], "y"))
            x_distance = abs(row.distance(current_rows[-1], "x"))
            if x_distance != 0 and y_distance > Config.max_row_distance:
                # TODO: Add to config
                if len(current_rows) < min_row_count:
                    print("Dropped rows with too much distance:\n\t"
                          "Distance (x, y):", x_distance, y_distance,
                          "Rows:", [str(r) for r in current_rows])
                    current_rows = [row]
                    continue
                print(f"Distance between rows: {y_distance}")
                tables.append(Table(current_rows))
                current_rows = []
            current_rows.append(row)
        else:
            if current_rows:
                tables.append(Table(current_rows))
        return tables

    def to_timetable(self) -> TimeTable:
        from datastructures.internal.timetable import TimeTable

        return TimeTable.from_raw_table(self)

    def get_header_from_column(self, column: Column) -> str:
        # TODO: There should be only a single header row.
        for row in self.rows.of_type(RowType.HEADER):
            for i, field in enumerate(row, 1):
                next_field = row.fields[i] if i < len(row.fields) else None
                if not next_field or next_field.bbox.x0 >= column.bbox.x1:
                    return field.text

        return ""
