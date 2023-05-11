""" Contains Bounds used by the Table to determine the Fields that are part
of the same Row/Column. """

from __future__ import annotations

from _operator import attrgetter
from itertools import cycle
from typing import (
    Callable, cast, Iterable, Iterator, NamedTuple, TypeVar,
    )

from pdf2gtfs.datastructures.pdftable.bbox import BBox
from pdf2gtfs.datastructures.table.direction import Direction, E, N, S, W
from pdf2gtfs.datastructures.table.cell import C, Cs


B = TypeVar("B", bound="Bounds")
BoundArgs = NamedTuple("BoundArgs",
                       [("func", Callable[[Iterable[C]], C]), ("attr", str)])


# TODO NOW: Subclass BBox <-> Change bounds into PartialBBox?


class Bounds:
    """ Basic bounding box, that may not be bounding to all sides. """
    def __init__(self, n: float | None, w: float | None,
                 s: float | None, e: float | None) -> None:
        self._n = n
        self._w = w
        self._s = s
        self._e = e
        self._update_hbox()
        self._update_vbox()

    @property
    def n(self) -> float | None:
        """ The northern bound, i.e. y0/the lowest y coordinate. """
        return self._n

    @n.setter
    def n(self, value: float | None) -> None:
        self._n = value
        self._update_vbox()

    @property
    def s(self) -> float | None:
        """ The southern bound, i.e. y1/the largest y coordinate. """
        return self._s

    @s.setter
    def s(self, value: float | None) -> None:
        self._s = value
        self._update_vbox()

    @property
    def w(self) -> float | None:
        """ The western bound, i.e. x0/the lowest x coordinate. """
        return self._w

    @w.setter
    def w(self, value: float | None) -> None:
        self._w = value
        self._update_hbox()

    @property
    def e(self) -> float | None:
        """ The eastern bound, i.e. x1/the largest y coordinate. """
        return self._e

    @e.setter
    def e(self, value: float | None) -> None:
        self._e = value
        self._update_hbox()

    @property
    def hbox(self) -> BBox | None:
        """ The horizontal bounding box, using only w/e. """
        return self._hbox

    @property
    def vbox(self) -> BBox | None:
        """ The vertical bounding box, using only n/s. """
        return self._vbox

    def _update_hbox(self) -> None:
        if self.w is None or self.e is None:
            hbox = None
        else:
            hbox = BBox(self.w, -1, self.e, -1)
        self._hbox = hbox

    def _update_vbox(self) -> None:
        if self.n is None or self.s is None:
            vbox = None
        else:
            vbox = BBox(-1, self.n, -1, self.s)
        self._vbox = vbox

    def _within_h_bounds(self, bbox: BBox) -> bool:
        if self.hbox and self.hbox.is_h_overlap(bbox):
            return True
        if self.hbox:
            return False
        if self.w is not None and bbox.x1 <= self.w:
            return False
        if self.e is not None and bbox.x0 >= self.e:
            return False
        return True

    def _within_v_bounds(self, bbox: BBox) -> bool:
        if self.vbox and self.vbox.is_v_overlap(bbox):
            return True
        if self.vbox:
            return False
        if self.n is not None and bbox.y1 <= self.n:
            return False
        if self.s is not None and bbox.y0 >= self.s:
            return False
        return True

    def within_bounds(self, obj: C) -> bool:
        """ Check if the obj is within the bounds.

        If the hbox/vbox is None, that is, if at least one of the w/e or n/s
        coordinates is None, the check will not fail immediately.
        Instead, in that case only the existing (if any) coordinate will
        be checked.

        :param obj: The obj, which requires a bbox.
        :return: True if obj is within both the hbox and the vbox.
        """
        bbox = obj.bbox
        return self._within_h_bounds(bbox) and self._within_v_bounds(bbox)

    def merge(self, other: B) -> None:
        """ Merge the bounds, such that the resulting bounds contain both.

        :param other: The other bounds.
        """
        # n/w use min for lower bound, s/e use max for larger bound.
        for coord, func in zip("nswe", cycle((min, max))):
            vals = [v for v in [getattr(self, coord), getattr(other, coord)]]
            setattr(self, coord, func(vals, default=None))

    @staticmethod
    def get_bound_from_cells(args: BoundArgs | None, cells: Iterable[C]
                             ) -> float | None:
        """ Calculate a bound from cells using the provided args. """
        if args is None:
            return None
        cells = list(cells)
        cell = args.func(cells, key=attrgetter(f"bbox.{args.attr}"))
        return cast(float, attrgetter(f"bbox.{args.attr}")(cell))

    @classmethod
    def from_bboxes(cls, bboxes: list[BBox], *,
                    n: BoundArgs | None = None, w: BoundArgs | None = None,
                    s: BoundArgs | None = None, e: BoundArgs | None = None
                    ) -> B:
        """ Create new bounds from the bboxes, setting only the
        provided bounds. """
        def _bbox_to_bound(args: BoundArgs | None) -> float | None:
            if not args:
                return None

            minmax = args.func(bboxes, key=attrgetter(args.attr))

            return cast(float, attrgetter(args.attr)(minmax))

        return cls(n=_bbox_to_bound(n), w=_bbox_to_bound(w),
                   s=_bbox_to_bound(s), e=_bbox_to_bound(e))

    def _update_single_bound(
            self, which: str, args: BoundArgs, cells: list[C]) -> None:
        """ Update a single bound using the BoundArgs and the cells.

        which can be one of "n", "w", "s", "e".
        """
        setattr(self, which, self.get_bound_from_cells(args, cells))

    def __repr__(self) -> str:
        cls_name = self.__class__.__name__
        fmt = "{: >7.2f}"
        n = fmt.format(self.n) if self.n is not None else "None"
        w = fmt.format(self.w) if self.w is not None else "None"
        s = fmt.format(self.s) if self.s is not None else "None"
        e = fmt.format(self.e) if self.e is not None else "None"
        return f"{cls_name}(n={n}, w={w}, s={s}, e={e})"

    @classmethod
    def select_adjacent_cells(cls, border: list[BBox], cells: Iterator[C]
                              ) -> Cs:
        """ Select those cells, that are adjacent to factory cells.

        :param border: The Row/Col, that is used to determine if a cell
         is adjacent to the table.
        :param cells: The cells that are checked.
        :return: Those items of cells, which are adjacent to the table.
        """
        # Get the three basic bounds, which are dictated by row_or_col.
        bounds = cls.from_bboxes(list(border))
        cells = list(filter(bounds.within_bounds, cells))
        if not cells:
            return cells
        bounds.update_missing_bound(cells)
        # These are the cells that fit all bounds.
        minimal_cells = list(filter(bounds.within_bounds, cells))
        # Also try to add cells, that fit only three bounds, but are
        # overlapping with cells, that fit all four.
        overlap_func = ("is_h_overlap" if cls in [WBounds, EBounds]
                        else "is_v_overlap")
        within_bounds_cells = []
        for cell in cells:
            for min_cell in minimal_cells:
                if getattr(cell.bbox, overlap_func)(min_cell.bbox, 0.8):
                    within_bounds_cells.append(cell)
                    break
        sort_key = "bbox.x0" if cls in [SBounds, NBounds] else "bbox.y0"
        return list(sorted(within_bounds_cells, key=attrgetter(sort_key)))


class WBounds(Bounds):
    """ The western outer bounds of a table. Used when growing a table. """
    @classmethod
    def from_bboxes(cls, bboxes: list[BBox], **_) -> WBounds:
        n = BoundArgs(min, "y0")
        s = BoundArgs(max, "y1")
        e = BoundArgs(min, "x0")
        return super().from_bboxes(bboxes, n=n, s=s, e=e)

    def update_missing_bound(self, cells: list[C]) -> None:
        """
        Update the western bound, which was not created using the datacells.
        """
        args: BoundArgs = BoundArgs(max, "x0")
        self._update_single_bound("w", args, cells)


class EBounds(Bounds):
    """ The eastern outer bounds of a table. Used when growing a table. """
    @classmethod
    def from_bboxes(cls, bboxes: list[BBox], **_) -> EBounds:
        n = BoundArgs(min, "y0")
        s = BoundArgs(max, "y1")
        w = BoundArgs(max, "x1")
        return super().from_bboxes(bboxes, n=n, w=w, s=s)

    def update_missing_bound(self, cells: list[C]) -> None:
        """
        Update the eastern bound, which was not created using the datacells.
        """
        args: BoundArgs = BoundArgs(min, "x1")
        self._update_single_bound("e", args, cells)


class NBounds(Bounds):
    """ The northern outer bounds of a table. Used when growing a table. """
    @classmethod
    def from_bboxes(cls, bboxes: list[BBox], **_) -> NBounds:
        w = BoundArgs(min, "x0")
        s = BoundArgs(min, "y0")
        e = BoundArgs(max, "x1")
        return super().from_bboxes(bboxes, w=w, s=s, e=e)

    def update_missing_bound(self, cells: list[C]) -> None:
        """
        Update the eastern bound, which was not created using the datacells.
        """
        args: BoundArgs = BoundArgs(max, "y0")
        self._update_single_bound("n", args, cells)


class SBounds(Bounds):
    """ The southern outer bounds of a table. Used when growing a table. """
    @classmethod
    def from_bboxes(cls, bboxes: list[BBox], **_) -> SBounds:
        n = BoundArgs(max, "y1")
        w = BoundArgs(min, "x0")
        e = BoundArgs(max, "x1")
        return super().from_bboxes(bboxes, n=n, w=w, e=e)

    def update_missing_bound(self, cells: list[C]) -> None:
        """
        Update the eastern bound, which was not created using the datacells.
        """
        args: BoundArgs = BoundArgs(min, "y1")
        self._update_single_bound("s", args, cells)


def select_adjacent_cells(d: Direction, bboxes: list[BBox], cells: Cs) -> Cs:
    """ Get all cells adjacent in d to the given reference cells.

    :param d: The direction to check for adjacency in.
    :param bboxes: The bboxes used to check for adjacency.
    :param cells: The cells that are checked for adjacency.
    :return: The cells that are adjacent to ref_cells.
    """
    bound_cls = {N: NBounds, W: WBounds, S: SBounds, E: EBounds}[d]

    adjacent_cells = bound_cls.select_adjacent_cells(bboxes, iter(cells))

    normal = d.default_orientation.normal
    # Remove cells that are not overlapping with any reference cell.
    starter_id = 0
    for adj_cell in adjacent_cells:
        for i, bbox in enumerate(bboxes[starter_id:], starter_id):
            if adj_cell.bbox.is_overlap(normal.name.lower(), bbox, 0.8):
                break
        else:
            adjacent_cells.remove(adj_cell)
            break
        starter_id = i
    return adjacent_cells
