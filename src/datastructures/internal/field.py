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


def field_from_char(char: pd.Series) -> Field:
    return Field(char.x0, char.x1, char.y0, char.y1, char.text)
