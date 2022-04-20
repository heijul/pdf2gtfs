from dataclasses import dataclass

from datastructures.internal.field import Field


@dataclass
class Column(Field):
    pass


def column_from_field(field: Field, text: str = "-") -> Column:
    return Column(field.x0, field.x1, field.y0, field.y1, text)
