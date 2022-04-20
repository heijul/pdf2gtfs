import pandas as pd

from datastructures.internal import Field, Column


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
