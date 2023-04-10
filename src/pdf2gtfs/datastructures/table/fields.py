""" Contains the different table fields, used when constructing the tables. """

from __future__ import annotations

from typing import Type, TYPE_CHECKING, TypeVar

from pdfminer.layout import LTChar

from pdf2gtfs.datastructures.pdftable import Char
from pdf2gtfs.datastructures.pdftable.bbox import BBox, BBoxObject
from pdf2gtfs.datastructures.table.linked_list import LLNode

if TYPE_CHECKING:
    from pdf2gtfs.datastructures.table.container import Col, Row

ST = TypeVar("ST")
F = TypeVar("F", bound="TableField")


class TableField(LLNode[F], BBoxObject):
    """ A single field in a row/col of a table. """
    def __init__(self, chars: list[LTChar], page_height: float) -> None:
        super().__init__(bbox=None)
        self.chars = chars
        # TODO NOW: Move to _initialize; Check if chars are same font/fontsize.
        self.font = self.chars[0].font if self.chars else None
        self.fontsize = self.chars[0].fontsize if self.chars else None
        self.page_height = page_height
        self._col = None
        self._row = None
        self._initialize()

    @property
    def col(self) -> Col | None:
        """ The column this field is contained in. """
        return self._col

    @col.setter
    def col(self, col: Col | None) -> None:
        # TODO NOW: Add
        self._col = col

    @property
    def row(self) -> Row | None:
        """ The row this field is contained in. """
        return self._row

    @row.setter
    def row(self, row: Row | None) -> None:
        self._row = row

    def _initialize(self) -> None:
        self.set_bbox_from_chars()
        self.text = "".join([c.get_text() for c in self.chars]).strip()

    def set_bbox_from_chars(self) -> None:
        """ Use the chars of this field to construct the bbox. """
        from pdf2gtfs.reader import lt_char_to_dict

        if not self.chars:
            return

        bbox = BBox.from_char(
            Char(**lt_char_to_dict(self.chars[0], self.page_height)))
        self.bbox = bbox
        for ltchar in self.chars:
            char = Char(**lt_char_to_dict(ltchar, self.page_height))
            self.bbox.merge(BBox.from_char(char))

    def to_subtype(self, subtype: Type[ST]) -> ST:
        """ Transforms the field into one of a different type. """
        return subtype(chars=self.chars, page_height=self.page_height)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(text='{self.text}')"


class EmptyTableField(TableField):
    """ A field in a table, that does not contain any text. """
    def __init__(self, **kwargs) -> None:
        # An empty field can never contain any characters.
        kwargs.update(dict(chars=[], page_height=0))
        super().__init__(**kwargs)

    def _initialize(self) -> None:
        self.text = ""

    def set_bbox_from_col_and_row(self) -> None:
        """ Use the x/y of the col/row respectively, to set the bbox. """
        assert self.row and self.col
        self.bbox = BBox(self.col.bbox.x0, self.row.bbox.y0,
                         self.col.bbox.x1, self.row.bbox.y1)


class DataAnnotField(TableField):
    """ An annotation, that is directly adjacent to a data field. """
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.data_field: DataField | None = None


class DataField(TableField):
    """ A field of a table, which contains time data. """
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._annotations: list[DataAnnotField] = []
        self.col_id = -1
        self.row_id = -1

    @property
    def annotations(self) -> list[DataAnnotField]:
        """ A list of annotations for this data field. """
        return self._annotations

    @annotations.setter
    def annotations(self, fields: list[DataAnnotField]) -> None:
        for field in fields:
            field.data_field = self
        self._annotations = fields


class EmptyDataField(EmptyTableField, DataField):
    """ An empty field, that is surrounded by at least two
    data fields on opposite sides. """
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        del self.col_id
        del self.row_id


class RepeatField(DataField):
    """ Base class for fields that are part of a repeat column/row. """
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        del self.col_id
        del self.row_id


class RepeatTextField(RepeatField):
    """ The field containing the text before/after the repeat time. """
    pass


class RepeatValueField(RepeatField):
    """ The field, that contains the amount of time,
     at which service will be repeated. """
    pass
