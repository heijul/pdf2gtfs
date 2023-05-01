""" Provides the different Fields of a Table. """

from __future__ import annotations

import logging
from typing import Generator, Optional, TypeAlias, TypeVar

from pdfminer.layout import LTChar
from pdfminer.pdffont import PDFFont

from pdf2gtfs.datastructures.pdftable import Char
from pdf2gtfs.datastructures.pdftable.bbox import BBox, BBoxObject
from pdf2gtfs.datastructures.table.fieldtype import (
    EmptyFieldType, FieldType, T,
    )
from pdf2gtfs.datastructures.table.nodes import QuadNode
from pdf2gtfs.datastructures.table.direction import (
    Direction, H, Orientation, V, D,
    )
from pdf2gtfs.datastructures.table.quadlinkedlist import QLL


logger = logging.getLogger(__name__)


F = TypeVar("F", bound="Field")
OF = TypeVar("OF", bound=Optional["Field"])
Fs: TypeAlias = list[F]


def get_bbox_from_chars(
        lt_chars: list[LTChar], page_height: float) -> BBox | None:
    """ Use the chars of this field to construct a bbox. """
    from pdf2gtfs.reader import lt_char_to_dict

    if not lt_chars:
        return None
    chars = [Char(**lt_char_to_dict(char, page_height)) for char in lt_chars]
    bbox = BBox.from_bboxes([BBox.from_char(char) for char in chars])
    return bbox


class Field(QuadNode[F, OF], BBoxObject):
    """ A singl field in a table. """

    def __init__(self, text: str, bbox: BBox | None = None,
                 font: PDFFont | None = None, fontname: str | None = None,
                 fontsize: float | None = None,
                 ) -> None:
        super().__init__(bbox=bbox)
        self.text = text
        self.font = font
        self.fontname = fontname
        self.fontsize = fontsize
        self.type = FieldType(self)

    @staticmethod
    def from_lt_chars(lt_chars: list[LTChar], page_height: float) -> Field:
        text = "".join([c.get_text() for c in lt_chars]).strip()
        bbox = get_bbox_from_chars(lt_chars, page_height)
        font = lt_chars[0].font if lt_chars else None
        fontname = font.fontname if font else None
        fontsize = lt_chars[0].fontsize if lt_chars else None
        return Field(text, bbox, font, fontname, fontsize)

    def duplicate(self) -> F:
        return Field(
            self.text, self.bbox, self.font, self.fontname, self.fontsize)

    def get_type(self) -> T:
        if self.type.inferred_type:
            return self.type.inferred_type
        return self.type.guess_type()

    def has_type(self, *types: T) -> bool:
        if not self.type.possible_types:
            self.get_type()
        return any(typ in self.type.possible_types for typ in types)

    def get_neighbors(self, *,
                      allow_none: bool = False, allow_empty: bool = True,
                      directions: list[Direction] = None
                      ) -> Fs:
        if directions is None:
            directions = D
        neighbors = {d: self.get_neighbor(d) for d in directions}
        # Find the next neighbor if the direct neighbor is an EmptyField.
        if not allow_empty:
            for d, neighbor in neighbors.items():
                if neighbor is None or not isinstance(neighbor, EmptyField):
                    continue
                while neighbor and isinstance(neighbor, EmptyField):
                    neighbor = neighbor.get_neighbor(d)
                neighbors[d] = neighbor
        # Remove neighbors that are None if allow_none is False.
        return [n for n in neighbors.values() if allow_none or n is not None]

    @property
    def row(self) -> Generator[F, None, None]:
        """ The row this field belongs to.

        :return: A generator over all objects in this fields' row.
        """
        return self.qll.get_series(H, self)

    @property
    def col(self) -> Generator[F, None, None]:
        """ The column this field belongs to.

        :return: A generator over all objects in this fields' column.
        """
        return self.qll.get_series(V, self)

    def any_overlap(self, o: Orientation, field: F) -> bool:
        """ Returns if there is any overlap between self and field in o.

        :param o: The orientation to check for overlap in.
        :param field: The field that is checked.
        :return: Whether there is any overlap between the field and self.
        """
        if o is V:
            return self.bbox.v_overlap(field) > 0
        return self.bbox.h_overlap(field) > 0

    def is_overlap(self, o: Orientation, field: F, *args) -> bool:
        """ Run is_v_overlap or is_h_overlap on field based on o.

        :param o: The orientation used to determine which method to run.
        :param field: The field passed to the method.
        :param args: Args to the method.
        :return: The output of the run method.
        """
        if o is V:
            return self.bbox.is_v_overlap(field.bbox, *args)
        return self.bbox.is_h_overlap(field.bbox, *args)

    def merge(self, field: F, *, merge_char: str = " ",
              ignore: list[Direction] = None) -> None:
        """ Merge field's contents to ours. The neighbors of the field will
            be our neighbors after merging.

        :param field: The field that will be merged.
        :param merge_char: The char used when merging the field text.
        :param ignore: The directions to ignore the neighbors in. Used, when
            multiple neighboring fields are being merged successively.
        """
        self.bbox.merge(field.bbox)
        self.text += f"{merge_char}{field.text}"
        for d in D:
            if ignore and d in ignore:
                continue
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
                               for d in D
                               for n in [self.get_neighbor(d)]
                               if n])
        return f"{self.__class__.__name__}(text='{self.text}', {neighbors})"


class EmptyField(Field, BBoxObject):
    """ A field in a table, that does not contain any text. """
    def __init__(self, **kwargs) -> None:
        # An empty field can never contain any characters.
        kwargs.update(dict(text="", bbox=None))
        super().__init__(**kwargs)
        self.type = EmptyFieldType(self)
        self._bbox = None

    def set_bbox_from_reference_fields(self, x_axis: F, y_axis: F) -> None:
        """ Set the bbox based on the two given fields.

        :param x_axis: This fields bbox's x-coordinates are used.
        :param y_axis: This fields bbox's y-coordinates are used.
        """
        self.bbox = BBox(x_axis.bbox.x0, y_axis.bbox.y0,
                         x_axis.bbox.x1, y_axis.bbox.y1)

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
