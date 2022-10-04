""" Types used by the Field, Row and Column. """

from enum import Enum


class FieldContainerType(Enum):
    """ Base class for container types. """
    pass


class RowType(FieldContainerType):
    """ The type of a row. Determined by the FieldType of its fields. """
    HEADER = 1
    DATA = 2
    OTHER = 3
    ANNOTATION = 4
    ROUTE_INFO = 5


class ColumnType(FieldContainerType):
    """ The type of a column. Determined by the FieldType of its fields. """
    STOP = 1
    STOP_ANNOTATION = 2
    DATA = 3
    REPEAT = 4
    OTHER = 5


class FieldType(Enum):
    """ The type of a field. Determined by the fields contents. """
    DATA = 0
    HEADER = 1
    STOP = 2
    STOP_ANNOT = 3
    ROW_ANNOT = 4
    ROUTE_INFO = 5
    REPEAT = 6
    OTHER = 7


class FieldValue(Enum):
    """ The type of the content of a field. """
    TIME_DATA = 0
    HEADER = 1
    ROW_ANNOT = 2
    ROUTE_INFO = 3
    REPEAT = 4
    STOP_ANNOT = 5
