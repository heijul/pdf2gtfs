""" Provides the different Bounds that are used by the Table to determine
the Cells that are adjacent to the Table. """

from __future__ import annotations

from _operator import attrgetter
from itertools import cycle
from typing import Callable, cast, Iterable, NamedTuple, Protocol, TypeVar

from pdf2gtfs.datastructures.pdftable.bbox import BBox
from pdf2gtfs.datastructures.table.direction import Direction, E, N, S, W
from pdf2gtfs.datastructures.table.cell import C, Cs


B = TypeVar("B", bound="Bounds")


class F(Protocol):
    """ Used as a type to typecheck min/max functions correctly. """
    def __call__(self, cells: Iterable[C] | Iterable[BBox],
                 key: Callable[[C | BBox], float]) -> C:
        pass


# Arguments used by the N-/S-/W-/EBounds.
#  — func: The function (min / max) used to determine the correct limit.
#  — direction: The Direction of the limit.
BoundArg = NamedTuple("BoundArg", [("func", F), ("direction", Direction)])


class Bounds:
    """ Basic Bounds, where not all limits necessarily exist. """
    d: Direction = None

    def __init__(self, n: float | None, w: float | None,
                 s: float | None, e: float | None) -> None:
        self._n = n
        self._w = w
        self._s = s
        self._e = e
        self._update_hbox()
        self._update_vbox()

    @classmethod
    def from_bboxes(cls, bboxes: list[BBox], *,
                    n: BoundArg | None = None, w: BoundArg | None = None,
                    s: BoundArg | None = None, e: BoundArg | None = None
                    ) -> B:
        """ Create a new Bounds from the BBoxes, based on which args are given.

        :param bboxes: The BBoxes used for construction.
        :param n: The northern BoundArg. None for NBounds.
        :param w: The western BoundArg. None for WBounds.
        :param s: The southern BoundArg. None for SBounds.
        :param e: The eastern BoundArg. None for EBounds.
        :return: A new Bounds created from the given BBoxes,
            based on which BoundArgs are provided.
        """
        return cls(n=get_limit_from_cells(bboxes, n),
                   w=get_limit_from_cells(bboxes, w),
                   s=get_limit_from_cells(bboxes, s),
                   e=get_limit_from_cells(bboxes, e))

    @classmethod
    def select_adjacent_cells(cls, border: list[BBox], cells: Cs) -> Cs:
        """ Select those Cells that are adjacent to the border BBoxes.

        :param border: The row/col of a Table that is used to determine
            if a Cell is adjacent to the Table.
        :param cells: The Cells that are checked for adjacency.
        :return: Those Cells, which are adjacent to the Table.
        """
        def within_min_cells(cell: C) -> bool:
            """ Check if the given Cell overlaps with any min_cells.

            The overlap function is determined by cls.

            :param cell: The Cell that is checked.
            :return: True if the Cell overlaps. False, otherwise.
            """
            func = getattr(cell.bbox, cls.d.o.overlap_func)
            for min_cell in min_cells:
                if func(min_cell.bbox, 0.8):
                    return True
            return False

        # Get the three basic bounds, which are created from the border.
        bounds = cls.from_bboxes(border)
        cells = list(filter(bounds.within_bounds, cells))
        if not cells:
            return cells

        bounds.update_missing_bound(cells)

        # These are the Cells that fit all bounds.
        min_cells = list(filter(bounds.within_bounds, cells))

        # Also add Cells that fit only three bounds,
        #  but are overlapping with Cells that fit all four.
        within_bounds_cells = [c for c in cells if within_min_cells(c)]

        # Sort columns by y0 and rows by x0.
        lower_coord = attrgetter(f"bbox.{cls.d.o.normal.lower.coordinate}")
        return list(sorted(within_bounds_cells, key=lower_coord))

    @property
    def n(self) -> float | None:
        """ The northern bound, i.e., y0/the lowest y coordinate. """
        return self._n

    @n.setter
    def n(self, value: float | None) -> None:
        self._n = value
        self._update_vbox()

    @property
    def s(self) -> float | None:
        """ The southern bound, i.e., y1/the largest y coordinate. """
        return self._s

    @s.setter
    def s(self, value: float | None) -> None:
        self._s = value
        self._update_vbox()

    @property
    def w(self) -> float | None:
        """ The western bound, i.e., x0/the lowest x coordinate. """
        return self._w

    @w.setter
    def w(self, value: float | None) -> None:
        self._w = value
        self._update_hbox()

    @property
    def e(self) -> float | None:
        """ The eastern bound, i.e., x1/the largest y coordinate. """
        return self._e

    @e.setter
    def e(self, value: float | None) -> None:
        self._e = value
        self._update_hbox()

    @property
    def hbox(self) -> BBox | None:
        """ The horizontal BBox, using only w/e. """
        return self._hbox

    @property
    def vbox(self) -> BBox | None:
        """ The vertical BBox, using only n/s. """
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

    def within_h_bounds(self, bbox: BBox) -> bool:
        """ Check if the given BBox is within the current Bounds, horizontally.

        :param bbox: The BBox that is checked.
        :return: True if the BBox is within Bounds. False, otherwise.
        """
        if self.hbox and self.hbox.is_h_overlap(bbox):
            return True
        if self.hbox:
            return False
        if self.w is not None and bbox.x1 <= self.w:
            return False
        if self.e is not None and bbox.x0 >= self.e:
            return False
        return True

    def within_v_bounds(self, bbox: BBox) -> bool:
        """ Check if the given BBox is within the current Bounds, vertically.

        :param bbox: The BBox that is checked.
        :return: True if the BBox is within Bounds. False, otherwise.
        """
        if self.vbox and self.vbox.is_v_overlap(bbox):
            return True
        if self.vbox:
            return False
        if self.n is not None and bbox.y1 <= self.n:
            return False
        if self.s is not None and bbox.y0 >= self.s:
            return False
        return True

    def within_bounds(self, cell: C) -> bool:
        """ Check if the Cell is within the bounds.

        If the hbox/vbox is None, that is, if at least one of the w/e or n/s
        coordinates is None, the check will not fail immediately.
        Instead, in that case, only the existing (if any) coordinate will
        be checked.

        :param cell: The Cell that is checked.
        :return: True, if obj is within both the hbox and the vbox.
            False, otherwise.
        """
        bbox = cell.bbox
        return self.within_h_bounds(bbox) and self.within_v_bounds(bbox)

    def merge(self, bounds: B) -> None:
        """ Merge the Bounds, such that the resulting Bounds contain both.

        :param bounds: The Bounds that is merged into this one.
        """
        # n/w use min for lower bound, s/e use max for larger bound.
        for coordinate, func in zip("nswe", cycle((min, max))):
            getter = attrgetter(coordinate)
            value = func(map(getter, (self, bounds)), default=None)
            setattr(self, coordinate, value)

    def _update_single_limit(
            self, which: str, arg: BoundArg, cells: list[C]) -> None:
        """ Update a single bound using the BoundArg and the Cells.

        :param which: Can be one of "n", "w", "s", "e".
        :param arg: The BoundArg that is used to determine the limit.
        :param cells: The Cells used to calculate the limit.
        """
        setattr(self, which, get_limit_from_cells(cells, arg))

    def __repr__(self) -> str:
        cls_name = self.__class__.__name__
        fmt = "{: >7.2f}"
        n = fmt.format(self.n) if self.n is not None else "None"
        w = fmt.format(self.w) if self.w is not None else "None"
        s = fmt.format(self.s) if self.s is not None else "None"
        e = fmt.format(self.e) if self.e is not None else "None"
        return f"{cls_name}(n={n}, w={w}, s={s}, e={e})"


class WBounds(Bounds):
    """ The western outer bounds of a Table. Used when expanding a Table. """
    d = W

    @classmethod
    def from_bboxes(cls, bboxes: list[BBox], **_) -> WBounds:
        n = BoundArg(min, N)
        s = BoundArg(max, S)
        # We use the opposite Direction here, because we want the outer Bounds.
        e = BoundArg(min, E.opposite)
        return super().from_bboxes(bboxes, n=n, s=s, e=e)

    def update_missing_bound(self, cells: list[C]) -> None:
        """ Add the missing bound (western) based on the given Cells. """
        args: BoundArg = BoundArg(max, W)
        self._update_single_limit("w", args, cells)


class EBounds(Bounds):
    """ The eastern outer bounds of a Table. Used when expanding a Table. """
    d = E

    @classmethod
    def from_bboxes(cls, bboxes: list[BBox], **_) -> EBounds:
        n = BoundArg(min, N)
        s = BoundArg(max, S)
        # We use the opposite Direction here, because we want the outer Bounds.
        w = BoundArg(max, W.opposite)
        return super().from_bboxes(bboxes, n=n, w=w, s=s)

    def update_missing_bound(self, cells: list[C]) -> None:
        """ Add the missing bound (eastern) based on the given ells. """
        args: BoundArg = BoundArg(min, E)
        self._update_single_limit("e", args, cells)


class NBounds(Bounds):
    """ The northern outer bounds of a Table. Used when expanding a Table. """
    d = N

    @classmethod
    def from_bboxes(cls, bboxes: list[BBox], **_) -> NBounds:
        w = BoundArg(min, W)
        # We use the opposite Direction here, because we want the outer Bounds.
        s = BoundArg(min, S.opposite)
        e = BoundArg(max, E)
        return super().from_bboxes(bboxes, w=w, s=s, e=e)

    def update_missing_bound(self, cells: list[C]) -> None:
        """ Add the missing bound (northern) based on the given Cells. """
        args: BoundArg = BoundArg(max, N)
        self._update_single_limit("n", args, cells)


class SBounds(Bounds):
    """ The southern outer bounds of a Table. Used when expanding a Table. """
    d = S

    @classmethod
    def from_bboxes(cls, bboxes: list[BBox], **_) -> SBounds:
        # We use the opposite Direction here, because we want the outer Bounds.
        n = BoundArg(max, N.opposite)
        w = BoundArg(min, W)
        e = BoundArg(max, E)
        return super().from_bboxes(bboxes, n=n, w=w, e=e)

    def update_missing_bound(self, cells: list[C]) -> None:
        """ Add the missing bound (southern) based on the given Cells. """
        args: BoundArg = BoundArg(min, S)
        self._update_single_limit("s", args, cells)


def get_limit_from_cells(objects: list[C] | list[BBox], arg: BoundArg | None
                         ) -> float | None:
    """ Calculate a limit from the Cells using the provided func and attr.

    :param objects: The Cells/BBoxes used to calculate the limit.
    :param arg: The BoundArg used to determine the limit.
    :return: The limit of the Cells, based on the given func and d.
    """
    if not objects or not arg:
        return None

    prefix = "bbox." if hasattr(objects[0], "bbox") else ""
    getter = attrgetter(prefix + arg.direction.coordinate)

    # Get the Cell/BBox that has the highest/lowest value for c.
    limit = arg.func(objects, key=getter)
    # Get the actual value.
    return cast(float, getter(limit))


def select_adjacent_cells(d: Direction, bboxes: list[BBox], cells: Cs) -> Cs:
    """ Get all Cells adjacent in d to the given reference Cells.

    :param d: The Direction to check for adjacency in.
    :param bboxes: The BBoxes used to check for adjacency.
    :param cells: The Cells that are checked for adjacency.
    :return: The Cells that are adjacent to ref_cells.
    """
    bound_cls = {N: NBounds, W: WBounds, S: SBounds, E: EBounds}[d]

    adjacent_cells = bound_cls.select_adjacent_cells(bboxes, cells)

    normal = d.o.normal
    # Remove Cells that are not overlapping with any reference Cell.
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
