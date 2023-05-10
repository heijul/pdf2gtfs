""" Provides the different Fields of a Table. """

from __future__ import annotations

import logging
from typing import Generator, Optional, TYPE_CHECKING, TypeAlias, TypeVar

from pdfminer.layout import LTChar
from pdfminer.pdffont import PDFFont

from pdf2gtfs.datastructures.pdftable import Char
from pdf2gtfs.datastructures.pdftable.bbox import BBox, BBoxObject
from pdf2gtfs.datastructures.table.fieldtype import (
    EmptyFieldType, FieldType, T,
    )
from pdf2gtfs.datastructures.table.direction import (
    Direction, E, H, N, Orientation, S, V, D, W,
    )

if TYPE_CHECKING:
    from pdf2gtfs.datastructures.table.table import Table


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


class Field(BBoxObject):
    """ A singl field in a table. """

    def __init__(self, text: str, bbox: BBox | None = None,
                 font: PDFFont | None = None, fontname: str | None = None,
                 fontsize: float | None = None,
                 ) -> None:
        super().__init__(bbox=bbox)
        self._list = None
        self._prev = None
        self._next = None
        self._above = None
        self._below = None
        self.text = text.strip()
        self.font = font
        self.fontname = fontname
        self.fontsize = fontsize
        self.type = FieldType(self)

    @property
    def prev(self) -> OF:
        """ The previous node (i.e. left of this one) or None. """
        return self.get_neighbor(W)

    @prev.setter
    def prev(self, node: OF) -> None:
        self.set_neighbor(W, node)

    @property
    def next(self) -> OF:
        """ The next node (i.e. right of this one) or None. """
        return self.get_neighbor(E)

    @next.setter
    def next(self, node: OF) -> None:
        self.set_neighbor(E, node)

    @property
    def above(self) -> OF:
        """ The node above this one or None. """
        return self.get_neighbor(N)

    @above.setter
    def above(self, node: OF) -> None:
        self.set_neighbor(N, node)

    @property
    def below(self) -> OF:
        """ The node below this one or None. """
        return self.get_neighbor(S)

    @below.setter
    def below(self, node: OF) -> None:
        self.set_neighbor(S, node)

    def get_neighbor(self, d: Direction) -> OF:
        """ Get the next neighbor in one of the four directions.

        :param d: The direction.
        :return: This nodes next neighbor in the given direction.
        """
        return getattr(self, d.p_attr)

    def set_neighbor(self, d: Direction, neighbor: OF) -> None:
        """ Update the neighbor in the given direction.

        This should **always** be called from the node the neighbor is
        moved to.

        If the current node already has a neighbor N in the given direction,
        N will be accessible by using `neighbor.get_neighbor(d)` afterwards.

        :param d: The direction the neighbor will be placed in.
        :param neighbor: The new neighbor or None.
        """
        current_neighbor: OF = self.get_neighbor(d)
        if not neighbor:
            setattr(self, d.p_attr, None)
            if current_neighbor:
                setattr(current_neighbor, d.opposite.p_attr, None)
            return

        setattr(self, d.p_attr, neighbor)
        setattr(neighbor, d.opposite.p_attr, self)
        neighbor.table = self.table
        if current_neighbor:
            setattr(neighbor, d.p_attr, current_neighbor)
            setattr(current_neighbor, d.opposite.p_attr, neighbor)

    def has_neighbors(self, *, d: Direction = None, o: Orientation = None
                      ) -> bool:
        """ Whether the node has any neighbors in the direction/orientation.

        Only exactly one of d/o can be given at a time.
        :param d: The direction to check for neighbors in.
        :param o: The orientation. Simply checks both directions of o.
        :return: True if there exist any neighbors, False otherwise.
        """
        # Exactly one of d/o is required.
        assert d is None or o is None
        assert d is not None or o is not None
        if o:
            return (self.has_neighbors(d=o.lower) or
                    self.has_neighbors(d=o.upper))
        return self.get_neighbor(d) is not None

    @property
    def table(self) -> Table | None:
        """ The QuadLinkedList, this node belongs to, if any. """
        return self._list

    @table.setter
    def table(self, quad_linked_list: Table | None) -> None:
        self._list = quad_linked_list

    def iter(self, d: Direction) -> Generator[F]:
        """ Return an Iterator over the neighbors of this field in the given d.

        This node will always be the first node yielded, i.e. no neighbor in
            the opposite direction of d will be returned.

        :param d:
        """
        field = self
        while field:
            yield field
            field = field.get_neighbor(d)

    @staticmethod
    def from_lt_chars(lt_chars: list[LTChar], page_height: float) -> Field:
        """ Create a new field from the given chars.

        :param lt_chars: The chars this field should contain.
        :param page_height: Required for the bbox creation.
        :return: A field that contains all given chars.
        """
        text = "".join([c.get_text() for c in lt_chars]).strip()
        bbox = get_bbox_from_chars(lt_chars, page_height)
        font = lt_chars[0].font if lt_chars else None
        fontname = font.fontname if font else None
        fontsize = lt_chars[0].fontsize if lt_chars else None
        return Field(text, bbox, font, fontname, fontsize)

    def duplicate(self) -> F:
        """ Duplicate the field (except for table and type).

        :return: A new field that has the same values.
        """
        return Field(
            self.text, self.bbox, self.font, self.fontname, self.fontsize)

    def get_type(self) -> T:
        """ The inferred or guessed type of the field, whichever exists. """
        if self.type.inferred_type:
            return self.type.inferred_type
        return self.type.guess_type()

    def has_type(self, *types: T) -> bool:
        """ Check if the field has any of the given types.

        :param types: Each of these will be checked.
        :return: True, if the fields' type is equal to any of the given types.
            False, otherwise.
        """
        if not self.type.possible_types:
            self.get_type()
        return any(typ in self.type.possible_types for typ in types)

    def get_neighbors(self, *,
                      allow_none: bool = False, allow_empty: bool = True,
                      directions: list[Direction] = None
                      ) -> Fs:
        """ Return the adjacent neighbors of the field.

        Depending on the parameters, the neighbors may not be adjacent.

        :param allow_none: Whether to return None for non-existent neighbors.
        :param allow_empty: If this is False, instead of returning EmptyFields,
            we will search for non-empty fields.
            If true, return any EmptyField.
        :param directions: The directions to look for neighbors in.
        :return: A list of some or all neighbors in the given directions.
        """
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
        if self.table:
            return self.table.get_series(H, self)
        node = self
        while node.prev:
            node = node.prev
        return node.iter(E)

    @property
    def col(self) -> Generator[F, None, None]:
        """ The column this field belongs to.

        :return: A generator over all objects in this fields' column.
        """
        if self.table:
            return self.table.get_series(V, self)
        node = self
        while node.above:
            node = node.above
        return node.iter(S)

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

        :param o: The orientation used to determine, which method to run.
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

    def get_last(self, d: Direction) -> F:
        """ The last neighbor that only has neighbors in d.opposite.

        :param d: The direction to look for.
        :return: The last field of the given direction.
         That is, the field that has no neighbor d.
        """
        field = self
        while field.has_neighbors(d=d):
            field = field.get_neighbor(d)
        return field

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

        :param x_axis: This fields' bbox's x-coordinates are used.
        :param y_axis: This fields' bbox's y-coordinates are used.
        """
        self.bbox = BBox(x_axis.bbox.x0, y_axis.bbox.y0,
                         x_axis.bbox.x1, y_axis.bbox.y1)

    @Field.table.setter
    def table(self, value: Table) -> None:
        if value:
            self._bbox = None
        Field.table.fset(self, value)

    @property
    def bbox(self) -> BBox:
        if self.table:
            return self.table.get_empty_field_bbox(self)
        if self._bbox:
            return self._bbox
        logger.warning("Tried to get the bbox of an empty field "
                       "that is not part of a table.")

    @bbox.setter
    def bbox(self, bbox: BBox | None) -> None:
        if not self.table:
            self._bbox = bbox
            return
        logger.warning("Tried to set the bbox of an empty field "
                       "that is part of a table.")
