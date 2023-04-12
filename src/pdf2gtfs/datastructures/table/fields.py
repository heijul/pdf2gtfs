""" Provides the different Fields of a Table. """
import logging
from typing import Generator, Optional, TypeAlias, TypeVar

from pdfminer.layout import LTChar

from pdf2gtfs.datastructures.pdftable import Char
from pdf2gtfs.datastructures.pdftable.bbox import BBox, BBoxObject
from pdf2gtfs.datastructures.table.nodes import QuadNode
from pdf2gtfs.datastructures.table.direction import (
    E, H, N, Orientation, S, V, W,
    )
from pdf2gtfs.datastructures.table.quadlinkedlist import QLL


logger = logging.getLogger(__name__)


F = TypeVar("F", bound="Field")
OF = TypeVar("OF", bound=Optional["Field"])
Fs: TypeAlias = list[F]


class Field(QuadNode[F, OF], BBoxObject):
    """ A singl field in a table. """

    def __init__(self, chars: list[LTChar], page_height: float) -> None:
        super().__init__(bbox=None)
        self.chars = chars
        self.page_height = page_height
        self.font = self.chars[0].font if self.chars else None
        self.fontname = self.chars[0].fontname if self.chars else None
        self.fontsize = self.chars[0].fontsize if self.chars else None
        self._initialize()

    def _initialize(self) -> None:
        self.set_bbox_from_chars()
        self.text = "".join([c.get_text() for c in self.chars]).strip()

    def set_bbox_from_chars(self) -> None:
        """ Use the chars of this field to construct the bbox. """
        from pdf2gtfs.reader import lt_char_to_dict

        if not self.chars:
            return
        bbox = BBox.from_bboxes([
            BBox.from_char(Char(**lt_char_to_dict(char, self.page_height)))
            for char in self.chars])
        self.bbox = bbox

    @property
    def row(self) -> Generator[F, None, None]:
        """ The row this field belongs to.

        :return: A generator over all objects in this fields' row.
        """
        return self.qll.row(self)

    @property
    def col(self) -> Generator[F, None, None]:
        """ The column this field belongs to.

        :return: A generator over all objects in this fields' column.
        """
        return self.qll.row(self)

    def any_overlap(self, o: Orientation, field: F) -> float:
        if o is V:
            return self.bbox.v_overlap(field) > 0
        return self.bbox.h_overlap(field) > 0

    def is_overlap(self, o: Orientation, field: F, *args) -> bool:
        if o is V:
            return self.bbox.is_v_overlap(field.bbox, *args)
        return self.bbox.is_h_overlap(field.bbox, *args)

    def merge(self, field: F, *, merge_char: str = " ") -> None:
        self.chars += field.chars
        self.bbox.merge(field.bbox)
        self.text += f"{merge_char}{field.text}"
        for d in [N, S, W, E]:
            # Remove field as a neighbor
            self_neighbor = self.get_neighbor(d)
            if self_neighbor == field:
                self.set_neighbor(d, None)
            # Add fields neighbors as our own neighbors.
            field_neighbor = field.get_neighbor(d)
            if not field_neighbor or field_neighbor == self:
                continue
            assert not self_neighbor or self_neighbor == field
            self.set_neighbor(d, field_neighbor)

    def __repr__(self) -> str:
        neighbors = ", ".join([f"{d.name}='{n.text}'"
                               for d in [N, S, W, E]
                               for n in [self.get_neighbor(d)]
                               if n])
        return f"{self.__class__.__name__}(text='{self.text}', {neighbors})"


class EmptyField(Field, BBoxObject):
    """ A field in a table, that does not contain any text. """
    def __init__(self, **kwargs) -> None:
        # An empty field can never contain any characters.
        kwargs.update(dict(chars=[], page_height=0))
        super().__init__(**kwargs)
        self._bbox = None

    def set_bbox_from_chars(self) -> None:
        pass

    @QuadNode.qll.setter
    def qll(self, value: QLL) -> None:
        if value:
            self._bbox = None
        QuadNode.qll.fset(self, value)

    @property
    def bbox(self) -> BBox:
        if self.qll:
            return self.qll.get_empty_field_bbox(self)
        if self._bbox:
            return self._bbox
        logger.warning("Tried to get the bbox of an empty field "
                       "that is not part of a table.")

    @bbox.setter
    def bbox(self, bbox: BBox | None) -> None:
        if not self.qll:
            self._bbox = bbox
            return
        logger.warning("Tried to set the bbox of an empty field "
                       "that is part of a table.")

    def _initialize(self) -> None:
        self.text = ""

    def set_bbox_from_col_and_row(self) -> None:
        """ Use the x/y of the col/row respectively, to set the bbox. """
        assert self.qll
        row = self.qll.get_list(H)
        row_bbox = self.qll.get_bbox_of(row)
        col = self.qll.get_list(V)
        col_bbox = self.qll.get_bbox_of(col)
        assert row and col
        self.bbox = BBox(col_bbox.x0, row_bbox.y0, col_bbox.x1, row_bbox.y1)


class DataAnnotField(Field):
    """ An annotation, that is directly adjacent to a data field. """
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.data_field: DataField | None = None


class DataField(Field):
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


class EmptyDataField(EmptyField, DataField):
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
