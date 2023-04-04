from __future__ import annotations

from typing import Type, TypeVar

from pdfminer.layout import LTChar

from pdf2gtfs.datastructures.pdftable import Char
from pdf2gtfs.datastructures.pdftable.bbox import BBox, BBoxObject


T = TypeVar("T")
F = TypeVar("F", bound="TableField")


class TableField(BBoxObject):
    def __init__(self, chars: list[LTChar], page_height: float) -> None:
        super().__init__(None)
        self.chars = chars
        # TODO NOW: Move to _initialize; Check if chars are same font/fontsize.
        self.font = self.chars[0].font if self.chars else None
        self.fontsize = self.chars[0].fontsize if self.chars else None
        self.page_height = page_height
        self.owner = None
        self._next = None
        self._prev = None
        self._above = None
        self._below = None
        self._initialize()

    def _initialize(self) -> None:
        self.set_bbox_from_chars()
        self.text = "".join([c.get_text() for c in self.chars]).strip()

    def _set_neighbor(self, attr: str, ref_attr: str,
                      field: TableField | None) -> None:
        """ Ensure the neighbor is symmetric. """
        assert self != field
        assert attr.startswith("_") and not ref_attr.startswith("_")
        old_field = getattr(self, attr)
        setattr(self, attr, field)
        # Prevent dangling references.
        if old_field:
            setattr(old_field, ref_attr, None)
        if field is None or getattr(field, ref_attr) == self:
            return
        setattr(field, ref_attr, self)

    @property
    def next(self) -> TableField:
        return self._next

    @next.setter
    def next(self, field: TableField | None) -> None:
        self._set_neighbor("_next", "prev", field)

    @property
    def prev(self) -> TableField | None:
        return self._prev

    @prev.setter
    def prev(self, field: TableField | None) -> None:
        self._set_neighbor("_prev", "next", field)

    @property
    def above(self) -> TableField | None:
        return self._above

    @above.setter
    def above(self, field) -> None:
        self._set_neighbor("_above", "below", field)

    @property
    def below(self) -> TableField | None:
        return self._below

    @below.setter
    def below(self, field: TableField | None) -> None:
        self._set_neighbor("_below", "above", field)

    def set_bbox_from_chars(self) -> None:
        from pdf2gtfs.reader import lt_char_to_dict

        if not self.chars:
            return

        bbox = BBox.from_char(
            Char(**lt_char_to_dict(self.chars[0], self.page_height)))
        self.bbox = bbox
        for ltchar in self.chars:
            char = Char(**lt_char_to_dict(ltchar, self.page_height))
            self.bbox.merge(BBox.from_char(char))

    def to_subtype(self, subtype: Type[T]) -> T:
        return subtype(chars=self.chars, page_height=self.page_height)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(text='{self.text}')"


class EmptyTableField(TableField):
    def __init__(self, **kwargs) -> None:
        # An empty field can never contain any characters.
        kwargs.update(dict(chars=[], page_height=0))
        super().__init__(**kwargs)

    def _initialize(self) -> None:
        self.text = ""


class DataAnnotField(TableField):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.data_field: DataField | None = None


class DataField(TableField):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._annotations: list[DataAnnotField] = []
        self.col = -1
        self.row = -1

    @property
    def annotations(self) -> list[DataAnnotField]:
        return self._annotations

    @annotations.setter
    def annotations(self, fields: list[DataAnnotField]) -> None:
        for field in fields:
            field.data_field = self
        self._annotations = fields

    def __repr__(self) -> str:
        if not hasattr(self, "row") or not hasattr(self, "col"):
            return super().__repr__()
        return (f"{self.__class__.__name__}(row={self.row:>3},"
                f" col={self.col:>3}, text='{self.text}')")


class EmptyDataField(EmptyTableField, DataField):
    def __init__(self, row: int, col: int, **kwargs) -> None:
        super().__init__(**kwargs)
        # This will fail (as it should), when only one of row/col is provided.
        if row >= 0 or col >= 0:
            self.row = row
            self.col = col


class RepeatField(DataField):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        del self.col
        del self.row


class RepeatTextField(RepeatField):
    pass


class RepeatValueField(RepeatField):
    pass
