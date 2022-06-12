from enum import Enum


class FieldContainerType(Enum):
    pass


class RowType(FieldContainerType):
    HEADER = 1
    DATA = 2
    OTHER = 3
    ANNOTATION = 4
    ROUTE = 5


class ColumnType(FieldContainerType):
    STOP = 1
    STOP_ANNOTATION = 2
    DATA = 3
    REPEAT = 4

