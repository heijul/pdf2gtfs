""" Provides the different Fields of a Table. """

from __future__ import annotations

import logging
from typing import Generator, Optional, TYPE_CHECKING, TypeAlias, TypeVar

from pdfminer.layout import LTChar
from pdfminer.pdffont import PDFFont

from pdf2gtfs.datastructures.pdftable import Char
from pdf2gtfs.datastructures.pdftable.bbox import BBox, BBoxObject
from pdf2gtfs.datastructures.table.celltype import (
    EmptyCellType, CellType, T,
    )
from pdf2gtfs.datastructures.table.direction import (
    Direction, E, H, N, Orientation, S, V, D, W,
    )

if TYPE_CHECKING:
    from pdf2gtfs.datastructures.table.table import Table


logger = logging.getLogger(__name__)


C = TypeVar("C", bound="Cell")
OF = TypeVar("OF", bound=Optional["Cell"])
Cs: TypeAlias = list[C]


def get_bbox_from_chars(
        lt_chars: list[LTChar], page_height: float) -> BBox | None:
    """ Use the chars of this cell to construct a bbox. """
    from pdf2gtfs.reader import lt_char_to_dict

    if not lt_chars:
        return None
    chars = [Char(**lt_char_to_dict(char, page_height)) for char in lt_chars]
    bbox = BBox.from_bboxes([BBox.from_char(char) for char in chars])
    return bbox


class Cell(BBoxObject):
    """ A singl cell in a table. """

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
        self.type = CellType(self)

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

    def iter(self, d: Direction) -> Generator[C]:
        """ Return an Iterator over the neighbors of this cell in the given d.

        This node will always be the first node yielded, i.e. no neighbor in
            the opposite direction of d will be returned.

        :param d:
        """
        cell = self
        while cell:
            yield cell
            cell = cell.get_neighbor(d)

    @staticmethod
    def from_lt_chars(lt_chars: list[LTChar], page_height: float) -> Cell:
        """ Create a new cell from the given chars.

        :param lt_chars: The chars this cell should contain.
        :param page_height: Required for the bbox creation.
        :return: A cell that contains all given chars.
        """
        text = "".join([c.get_text() for c in lt_chars]).strip()
        bbox = get_bbox_from_chars(lt_chars, page_height)
        font = lt_chars[0].font if lt_chars else None
        fontname = font.fontname if font else None
        fontsize = lt_chars[0].fontsize if lt_chars else None
        return Cell(text, bbox, font, fontname, fontsize)

    def duplicate(self) -> C:
        """ Duplicate the cell (except for table and type).

        :return: A new cell that has the same values.
        """
        return Cell(
            self.text, self.bbox, self.font, self.fontname, self.fontsize)

    def get_type(self) -> T:
        """ The inferred or guessed type of the cell, whichever exists. """
        if self.type.inferred_type:
            return self.type.inferred_type
        return self.type.guess_type()

    def has_type(self, *types: T) -> bool:
        """ Check if the cell has any of the given types.

        :param types: Each of these will be checked.
        :return: True, if the cells' type is equal to any of the given types.
            False, otherwise.
        """
        if not self.type.possible_types:
            self.get_type()
        return any(typ in self.type.possible_types for typ in types)

    def get_neighbors(self, *,
                      allow_none: bool = False, allow_empty: bool = True,
                      directions: list[Direction] = None
                      ) -> Cs:
        """ Return the adjacent neighbors of the cell.

        Depending on the parameters, the neighbors may not be adjacent.

        :param allow_none: Whether to return None for non-existent neighbors.
        :param allow_empty: If this is False, instead of returning EmptyFields,
            we will search for non-empty cells.
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
                if neighbor is None or not isinstance(neighbor, EmptyCell):
                    continue
                while neighbor and isinstance(neighbor, EmptyCell):
                    neighbor = neighbor.get_neighbor(d)
                neighbors[d] = neighbor
        # Remove neighbors that are None if allow_none is False.
        return [n for n in neighbors.values() if allow_none or n is not None]

    @property
    def row(self) -> Generator[C, None, None]:
        """ The row this cell belongs to.

        :return: A generator over all objects in this cells' row.
        """
        if self.table:
            return self.table.get_series(H, self)
        node = self
        while node.prev:
            node = node.prev
        return node.iter(E)

    @property
    def col(self) -> Generator[C, None, None]:
        """ The column this cell belongs to.

        :return: A generator over all objects in this cells' column.
        """
        if self.table:
            return self.table.get_series(V, self)
        node = self
        while node.above:
            node = node.above
        return node.iter(S)

    def any_overlap(self, o: Orientation, cell: C) -> bool:
        """ Returns if there is any overlap between self and cell in o.

        :param o: The orientation to check for overlap in.
        :param cell: The cell that is checked.
        :return: Whether there is any overlap between the cell and self.
        """
        if o is V:
            return self.bbox.v_overlap(cell) > 0
        return self.bbox.h_overlap(cell) > 0

    def is_overlap(self, o: Orientation, cell: C, *args) -> bool:
        """ Run is_v_overlap or is_h_overlap on cell based on o.

        :param o: The orientation used to determine, which method to run.
        :param cell: The cell passed to the method.
        :param args: Args to the method.
        :return: The output of the run method.
        """
        if o is V:
            return self.bbox.is_v_overlap(cell.bbox, *args)
        return self.bbox.is_h_overlap(cell.bbox, *args)

    def merge(self, cell: C, *, merge_char: str = " ",
              ignore: list[Direction] = None) -> None:
        """ Merge cell's contents to ours. The neighbors of the cell will
            be our neighbors after merging.

        :param cell: The cell that will be merged.
        :param merge_char: The char used when merging the cell text.
        :param ignore: The directions to ignore the neighbors in. Used, when
            multiple neighboring cells are being merged successively.
        """
        self.bbox.merge(cell.bbox)
        self.text += f"{merge_char}{cell.text}"
        for d in D:
            if ignore and d in ignore:
                continue
            # Remove cell as a neighbor
            self_neighbor = self.get_neighbor(d)
            if self_neighbor == cell:
                self.set_neighbor(d, None)
            # Add cells neighbors as our own neighbors.
            cell_neighbor = cell.get_neighbor(d)
            if not cell_neighbor or cell_neighbor == self:
                continue
            assert not self_neighbor or self_neighbor == cell
            self.set_neighbor(d, cell_neighbor)

    def get_last(self, d: Direction) -> C:
        """ The last neighbor that only has neighbors in d.opposite.

        :param d: The direction to look for.
        :return: The last cell of the given direction.
         That is, the cell that has no neighbor d.
        """
        cell = self
        while cell.has_neighbors(d=d):
            cell = cell.get_neighbor(d)
        return cell

    def __repr__(self) -> str:
        neighbors = ", ".join([f"{d.name}='{n.text}'"
                               for d in D
                               for n in [self.get_neighbor(d)]
                               if n])
        return f"{self.__class__.__name__}(text='{self.text}', {neighbors})"


class EmptyCell(Cell, BBoxObject):
    """ A cell in a table, that does not contain any text. """
    def __init__(self, **kwargs) -> None:
        # An empty cell can never contain any characters.
        kwargs.update(dict(text="", bbox=None))
        super().__init__(**kwargs)
        self.type = EmptyCellType(self)
        self._bbox = None

    def set_bbox_from_reference_cells(self, x_axis: C, y_axis: C) -> None:
        """ Set the bbox based on the two given cells.

        :param x_axis: This cells' bbox's x-coordinates are used.
        :param y_axis: This cells' bbox's y-coordinates are used.
        """
        self.bbox = BBox(x_axis.bbox.x0, y_axis.bbox.y0,
                         x_axis.bbox.x1, y_axis.bbox.y1)

    @Cell.table.setter
    def table(self, value: Table) -> None:
        if value:
            self._bbox = None
        Cell.table.fset(self, value)

    @property
    def bbox(self) -> BBox:
        self.table: Table
        if self.table:
            return self.table.get_empty_cell_bbox(self)
        if self._bbox:
            return self._bbox
        logger.warning("Tried to get the bbox of an empty cell "
                       "that is not part of a table.")

    @bbox.setter
    def bbox(self, bbox: BBox | None) -> None:
        if not self.table:
            self._bbox = bbox
            return
        logger.warning("Tried to set the bbox of an empty cell "
                       "that is part of a table.")
