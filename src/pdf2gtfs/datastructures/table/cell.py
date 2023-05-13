""" Provides the different Cells of a Table. """

from __future__ import annotations

import logging
from typing import Generator, Optional, TYPE_CHECKING, TypeAlias, TypeVar

from pdfminer.layout import LTChar
from pdfminer.pdffont import PDFFont

from pdf2gtfs.datastructures.pdftable import Char
from pdf2gtfs.datastructures.pdftable.bbox import BBox, BBoxObject
from pdf2gtfs.datastructures.table.celltype import EmptyCellType, CellType, T
from pdf2gtfs.datastructures.table.direction import (
    Direction, E, N, Orientation, S, V, D, W,
    )

if TYPE_CHECKING:
    from pdf2gtfs.datastructures.table.table import Table


logger = logging.getLogger(__name__)


C = TypeVar("C", bound="Cell")
OC: TypeAlias = Optional[C]
Cs: TypeAlias = list[C]


def get_bbox_from_chars(lt_chars: list[LTChar], page_height: float) -> BBox:
    """ Construct a BBox from the given chars.

    :param lt_chars: The chars to construct the BBox from.
    :param page_height: The height of the current page.
    :return: A BBox that contains all the given chars.
    """
    from pdf2gtfs.reader import lt_char_to_dict

    chars = [Char(**lt_char_to_dict(char, page_height)) for char in lt_chars]
    bbox = BBox.from_bboxes([BBox.from_char(char) for char in chars])
    return bbox


class Cell(BBoxObject):
    """ A single cell in a table. """

    def __init__(self, text: str, bbox: BBox | None = None,
                 font: PDFFont | None = None, fontname: str | None = None,
                 fontsize: float | None = None,
                 ) -> None:
        super().__init__(bbox=bbox)
        self._table = None
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
    def prev(self) -> OC:
        """ The previous/left Cell, or None if this is the left-most Cell. """
        return self.get_neighbor(W)

    @prev.setter
    def prev(self, cell: OC) -> None:
        self.update_neighbor(W, cell)

    @property
    def next(self) -> OC:
        """ The next/right Cell, or None if this is the right-most Cell. """
        return self.get_neighbor(E)

    @next.setter
    def next(self, cell: OC) -> None:
        self.update_neighbor(E, cell)

    @property
    def above(self) -> OC:
        """ The Cell above this one, or None if this is the top Cell. """
        return self.get_neighbor(N)

    @above.setter
    def above(self, cell: OC) -> None:
        self.update_neighbor(N, cell)

    @property
    def below(self) -> OC:
        """ The Cell below this one, or None if this is the bottom Cell. """
        return self.get_neighbor(S)

    @below.setter
    def below(self, cell: OC) -> None:
        self.update_neighbor(S, cell)

    def get_neighbor(self, d: Direction) -> OC:
        """ Get the direct neighbor in the given Direction.

        :param d: The Direction.
        :return: This Cell's next/direct neighbor in the given Direction.
        """
        return getattr(self, d.p_attr)

    def del_neighbor(self, d: Direction) -> None:
        """ Remove the neighbor in the given Direction.

        :param d: Remove the neighbor that is located in this Direction.
        """
        current_neighbor: OC = self.get_neighbor(d)
        setattr(self, d.p_attr, None)
        if current_neighbor:
            setattr(current_neighbor, d.opposite.p_attr, None)

    def set_neighbor(self, d: Direction, cell: C) -> None:
        """ Set this Cell's neighbor in the given Direction to the given Cell.

        :param d: The Direction of the Cell relative to self.
        :param cell: The Cell that will be the new neighbor.
        """
        assert cell is not None, "Use update_neighbor, if cell might be None"

        current_neighbor: OC = self.get_neighbor(d)

        setattr(self, d.p_attr, cell)
        setattr(cell, d.opposite.p_attr, self)
        cell.table = self.table
        # Set the current neighbor as neighbor of the new neighbor
        #  in the same Direction, to ensure not to break transitivity.
        if not current_neighbor:
            return
        setattr(cell, d.p_attr, current_neighbor)
        setattr(current_neighbor, d.opposite.p_attr, cell)

    def update_neighbor(self, d: Direction, neighbor: C | None) -> None:
        """ Update the neighbor in the given Direction.

        This should **always** be called from the Cell the neighbor is
        moved to.

        If the current Cell already has a neighbor N in the given Direction,
        N will be accessible by using `neighbor.get_neighbor(d)` afterward.

        :param d: The Direction the neighbor will be placed in.
        :param neighbor: The new neighbor
            or None, to remove the current neighbor.
        """
        if not neighbor:
            self.del_neighbor(d)
            return
        self.set_neighbor(d, neighbor)

    def has_neighbors(self, *, d: Direction = None, o: Orientation = None
                      ) -> bool:
        """ Whether this Cell has any neighbors in the Direction/Orientation.

        Only exactly one of d/o can be given at a time.

        :param d: The Direction to check for neighbors in.
        :param o: The Orientation to check for neighbors in.
            Simply checks both Directions of o.
        :return: True, if there exist any neighbors. False, otherwise.
        """
        if o is None:
            # Exactly one of d/o is required.
            assert d is not None
            return self.get_neighbor(d) is not None

        # Exactly one of d/o is required.
        assert d is None
        return self.has_neighbors(d=o.lower) or self.has_neighbors(d=o.upper)

    @property
    def table(self) -> Table | None:
        """ The Table that this Cell belongs to, if any. """
        return self._table

    @table.setter
    def table(self, table: Table | None) -> None:
        self._table = table

    def iter(self, d: Direction = None, complete: bool = True,
             *, o: Orientation = None) -> Generator[C]:
        """ Return an Iterator over the neighbors of this Cell in the given d.

        Only one of o and d must be given.

        :param d: The Direction to iterate over the Cells in.
        :param complete: If True, we first reverse the Direction. That way,
            this will return a generator over all neighbors of self, and self.
        :param o: The Orientation to use.
            I.e., whether to return row (H) or column (V).
            If given will iterate over the Cells using the upper Direction.
        :return: A generator over either all Cells in this Cell's row/col,
            or only those that are neighbors in the given Direction.
        """
        if o:
            assert d is None
            d = o.upper
        assert d is not None

        cell = self.get_last(d.opposite) if complete else self
        while cell:
            yield cell
            cell = cell.get_neighbor(d)

    @staticmethod
    def from_lt_chars(lt_chars: list[LTChar], page_height: float) -> Cell:
        """ Create a new Cell from the given chars.

        :param lt_chars: The chars the new Cell is created from.
        :param page_height: Height of the page. Required for the BBox creation.
        :return: A new Cell that contains the text of all given chars
            and a minimal BBox that contains all given chars.
        """
        text = "".join([c.get_text() for c in lt_chars]).strip()
        bbox = get_bbox_from_chars(lt_chars, page_height)
        font = lt_chars[0].font if lt_chars else None
        fontname = font.fontname if font else None
        fontsize = lt_chars[0].fontsize if lt_chars else None
        # A Cell contains only chars with equal font properties.
        assert all([font == char.font for char in lt_chars])
        assert all([fontname == char.fontname for char in lt_chars])
        assert all([fontsize == char.fontsize for char in lt_chars])

        return Cell(text, bbox, font, fontname, fontsize)

    def duplicate(self) -> C:
        """ Duplicate the Cell (except for table and type).

        :return: A new Cell that has the same values.
        """
        return Cell(self.text, self.bbox,
                    self.font, self.fontname, self.fontsize)

    def get_type(self) -> T:
        """ The inferred or guessed type of the Cell, whichever exists. """
        # Prefer the inferred CellType, if it exists.
        if self.type.inferred_type:
            return self.type.inferred_type
        return self.type.guess_type()

    def has_type(self, *types: T) -> bool:
        """ Check, if the Cell contains any of the types in its possible types.

        :param types: Any of these must be in the Cell's possible types.
        :return: True, if any of the given CellTypes is
            a possible type of the Cell. False, otherwise.
        """
        # PR: Add strict.
        if not self.type.possible_types:
            self.get_type()
        return any(typ in self.type.possible_types for typ in types)

    def get_neighbors(self, *,
                      allow_none: bool = False, allow_empty: bool = True,
                      directions: list[Direction] = D
                      ) -> Cs:
        """ Return neighbors of the Cell.

        Depending on the parameters, the neighbors may not be adjacent.

        :param allow_none: Whether to return None for non-existent neighbors.
        :param allow_empty: If true, return any EmptyCell, if it is a neighbor.
            If False, instead of returning the EmptyCells,
             we will search for non-empty Cells.
        :param directions: The Directions to look for neighbors in.
            If this is not given, search all Directions.
        :return: A list of some or all neighbors of this Cell.
        """
        neighbors = {d: self.get_neighbor(d) for d in directions}
        if not allow_empty:
            # Find the next neighbor, if the direct neighbor is an EmptyCell.
            for d, neighbor in neighbors.items():
                if neighbor is None or not isinstance(neighbor, EmptyCell):
                    continue
                while neighbor and isinstance(neighbor, EmptyCell):
                    neighbor = neighbor.get_neighbor(d)
                neighbors[d] = neighbor
        # Remove neighbors that are None, if allow_none is False.
        return [n for n in neighbors.values() if allow_none or n is not None]

    @property
    def row(self) -> Generator[C, None, None]:
        """ The row this Cell belongs to.

        :return: A generator over all Cells in this Cell's row.
        """
        return self.iter(E)

    @property
    def col(self) -> Generator[C, None, None]:
        """ The column this Cell belongs to.

        :return: A generator over all Cells in this Cell's column.
        """
        return self.iter(S)

    def any_overlap(self, o: Orientation, cell: C) -> bool:
        """ Check, if there is any overlap between self and the given Cell.

        :param o: The Orientation to check for overlap in.
        :param cell: The Cell that may be overlapping.
        :return: True, if there is any overlap between the Cell and self.
            False, otherwise.
        """
        # TODO: Use o.overlap_func (after moving it there from d) instead.
        if o is V:
            return self.bbox.v_overlap(cell) > 0
        return self.bbox.h_overlap(cell) > 0

    def is_overlap(self, o: Orientation, cell: C, *args) -> bool:
        """ Check if self and the given Cell are overlapping in the given o.

        :param o: The Orientation used to determine, which method to run.
        :param cell: The Cell that may be overlapping.
        :param args: Args passed to the overlap method.
        :return: True, if self and the given Cell overlap. False, otherwise.
        """
        if o is V:
            return self.bbox.is_v_overlap(cell.bbox, *args)
        return self.bbox.is_h_overlap(cell.bbox, *args)

    def merge(self, cell: C, *,
              merge_char: str = " ", ignore_neighbors: list[Direction] = None
              ) -> None:
        """ Merge the given Cell's contents with self's.

        The neighbors of the given Cell will be our neighbors after merging.

        :param cell: The Cell that will be merged.
        :param merge_char: The char used when merging the text of both Cells.
        :param ignore_neighbors: The Directions to ignore the neighbors in.
            Useful, when multiple neighboring Cells are merged successively.
        """
        self.bbox.merge(cell.bbox)
        self.text += f"{merge_char}{cell.text}"
        for d in D:
            if ignore_neighbors and d in ignore_neighbors:
                continue
            # Remove the given Cell as a neighbor.
            self_neighbor = self.get_neighbor(d)
            if self_neighbor == cell:
                self.del_neighbor(d)
            # Add the other Cell's neighbors as our own neighbors.
            cell_neighbor = cell.get_neighbor(d)
            if not cell_neighbor or cell_neighbor == self:
                continue
            assert not self_neighbor or self_neighbor == cell
            self.set_neighbor(d, cell_neighbor)

    def get_last(self, d: Direction) -> C:
        """ The last neighbor that only has neighbors (if any) in d.opposite.

        :param d: The Direction to look for.
        :return: The last Cell of the given Direction.
            That is, the Cell that has no neighbor d.
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
    """ A Cell in a table, that does not contain any text. """
    def __init__(self, **kwargs) -> None:
        # An EmptyCell can never contain any characters.
        kwargs.update(dict(text="", bbox=None))
        super().__init__(**kwargs)
        self.type = EmptyCellType(self)
        self._bbox = None

    def set_bbox_from_reference_cells(self, x_axis: C, y_axis: C) -> None:
        """ Set the bbox based on the two given Cells.

        :param x_axis: This Cell's bbox's x-coordinates are used.
        :param y_axis: This Cell's bbox's y-coordinates are used.
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
        """ The BBox of an EmptyCell is defined as its row's x-coordinates
        and its col's y-coordinates.

        :return: A BBox that is contained by both the row/col,
            while having the row's height and the col's width.
        """
        self.table: Table
        if self.table:
            row_bbox = self.table.get_bbox_of(self.row)
            col_bbox = self.table.get_bbox_of(self.col)
            return BBox(col_bbox.x0, row_bbox.y0, col_bbox.x1, row_bbox.y1)
        if self._bbox:
            return self._bbox
        logger.warning("Tried to get the bbox of an EmptyCell that is "
                       "not part of a Table.")

    @bbox.setter
    def bbox(self, bbox: BBox | None) -> None:
        if not self.table:
            self._bbox = bbox
            return
        logger.warning("Tried to set the bbox of an EmptyCell that is "
                       "part of a Table.")
