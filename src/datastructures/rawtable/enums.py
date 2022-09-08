from enum import Enum


class FieldContainerType(Enum):
    pass


class RowType(FieldContainerType):
    HEADER = 1
    DATA = 2
    OTHER = 3
    ANNOTATION = 4
    ROUTE_INFO = 5


class ColumnType(FieldContainerType):
    STOP = 1
    STOP_ANNOTATION = 2
    DATA = 3
    REPEAT = 4
    OTHER = 5


class FieldType(Enum):
    DATA = 0
    HEADER = 1
    STOP = 2
    STOP_ANNOT = 3
    ROW_ANNOT = 4
    ROUTE_INFO = 5
    REPEAT = 6
    OTHER = 7


class FieldValue(Enum):
    TIME_DATA = 0
    HEADER = 1
    ROW_ANNOT = 2
    ROUTE_INFO = 3
    REPEAT = 4
    STOP_ANNOT = 5
