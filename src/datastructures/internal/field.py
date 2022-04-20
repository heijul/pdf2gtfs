from dataclasses import dataclass

import pandas as pd

from utils import contains_bbox


@dataclass
class Field:
    x0: int
    x1: int
    y0: int
    y1: int
    text: str

    def add_char(self, char: pd.Series):
        self.x1 = max(self.x1, char.x1)
        self.y0 = min(self.y0, char.y0)
        self.y1 = max(self.y1, char.y1)
        self.text += char.text

    @property
    def bbox(self):
        return self.x0, self.y0, self.x1, self.y1

    def contains(self, other) -> bool:
        return contains_bbox(self.bbox, other.bbox)


@dataclass
class Column(Field):
    pass


def field_from_char(char: pd.Series) -> Field:
    return Field(char.x0, char.x1, char.y0, char.y1, char.text)


def field_text_generator(fields: list[Field], columns: list[Column]):
    """ Iterates through the columns and fields, returning the column text.

    If there is a field in that column, return its text,
    otherwise the default column text. If multiple fields
    are in the same column, their texts are joined with a space.
    """
    field_index = 0
    column_index = 0
    while field_index < len(fields) or column_index < len(columns):
        column = columns[column_index]
        column_index += 1
        text = ""
        # Needed in case multiple fields are within the current column
        while (field_index < len(fields)
               and column.contains(fields[field_index])):
            text += " " + fields[field_index].text
            field_index += 1
        text = text.strip()

        yield text if text else column.text
