""" Contains Bounds used by the Table to determine the Fields that are part
of the same Row/Column. """

from __future__ import annotations

from _operator import attrgetter
from functools import partial
from itertools import cycle
from typing import Callable, cast, Iterable, Iterator, NamedTuple, TypeVar

from pdf2gtfs.datastructures.pdftable.bbox import BBox
from pdf2gtfs.datastructures.table.fields2 import F, Fs


B = TypeVar("B", bound="Bounds")
# TODO: bbox_attr/return_attr appear to be always equal.
BoundArgs = NamedTuple("BoundArgs", [("func", Callable[[Iterable[F]], F]),
                                     ("bbox_attr", str),
                                     ("return_attr", str)])


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

    def within_bounds(self, obj: F) -> bool:
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
    def get_bound_from_fields(args: BoundArgs | None, fields: Iterable[F]
                              ) -> float | None:
        """ Calculate a bound from fields using the provided args. """
        if args is None:
            return None
        fields = list(fields)
        field = args.func(fields, key=attrgetter(f"bbox.{args.bbox_attr}"))
        return cast(float, attrgetter(f"bbox.{args.return_attr}")(field))

    @classmethod
    def from_factory_fields(cls, fields: Iterable[F],
                            *, n=None, w=None, s=None, e=None) -> B:
        """ Create new bounds from the fields, setting only the
        provided bounds. """
        func = partial(cls.get_bound_from_fields, fields=fields)
        return cls(n=func(n), w=func(w), s=func(s), e=func(e))

    def _update_single_bound(
            self, which: str, args: BoundArgs, fields: list[F]) -> None:
        """ Update a single bound using the BoundArgs and the fields.

        which can be one of "n", "w", "s", "e".
        """
        setattr(self, which, self.get_bound_from_fields(args, fields))

    def __repr__(self) -> str:
        cls_name = self.__class__.__name__
        fmt = "{:>7.2f}"
        n = fmt.format(self.n) if self.n is not None else "None"
        w = fmt.format(self.w) if self.w is not None else "None"
        s = fmt.format(self.s) if self.s is not None else "None"
        e = fmt.format(self.e) if self.e is not None else "None"
        return f"{cls_name}(n={n}, w={w}, s={s}, e={e})"

    @classmethod
    def select_adjacent_fields(cls, border: Fs, fields: Iterator[F]) -> Fs:
        """ Select those fields, that are adjacent to factory fields.

        :param row_or_col: The Row/Col, that is used to determine if a field
         is adjacent to the table.
        :param fields: The fields that are checked.
        :return: Those items of fields, which are adjacent to the table.
        """
        # Get the three basic bounds, which are dictated by row_or_col.
        bounds = cls.from_factory_fields(list(border))
        fields = list(filter(bounds.within_bounds, fields))
        if not fields:
            return fields
        bounds.update_missing_bound(fields)
        # These are the fields that fit all bounds.
        minimal_fields = list(filter(bounds.within_bounds, fields))
        # Also try to add fields, that fit only three bounds, but are
        # overlapping with fields, that fit all four.
        overlap_func = ("is_h_overlap" if cls in [WBounds, EBounds]
                        else "is_v_overlap")
        within_bounds_fields = []
        for field in fields:
            for min_field in minimal_fields:
                if getattr(field.bbox, overlap_func)(min_field.bbox, 0.8):
                    within_bounds_fields.append(field)
                    break
        sort_key = "bbox.x0" if cls in [SBounds, NBounds] else "bbox.y0"
        return list(sorted(within_bounds_fields, key=attrgetter(sort_key)))


class WBounds(Bounds):
    """ The western outer bounds of a table. Used when growing a table. """
    @classmethod
    def from_factory_fields(cls, fields: list[F], **_) -> WBounds:
        n = BoundArgs(min, "y0", "y0")
        s = BoundArgs(max, "y1", "y1")
        e = BoundArgs(min, "x0", "x0")
        return super().from_factory_fields(fields, n=n, s=s, e=e)

    def update_missing_bound(self, fields: list[F]) -> None:
        """
        Update the western bound, which was not created using the datafields.
        """
        args: BoundArgs = BoundArgs(max, "x0", "x0")
        self._update_single_bound("w", args, fields)


class EBounds(Bounds):
    """ The eastern outer bounds of a table. Used when growing a table. """
    @classmethod
    def from_factory_fields(cls, fields: list[F], **_) -> EBounds:
        n = BoundArgs(min, "y0", "y0")
        s = BoundArgs(max, "y1", "y1")
        w = BoundArgs(max, "x1", "x1")
        return super().from_factory_fields(fields, n=n, w=w, s=s)

    def update_missing_bound(self, fields: list[F]) -> None:
        """
        Update the eastern bound, which was not created using the datafields.
        """
        args: BoundArgs = BoundArgs(min, "x1", "x1")
        self._update_single_bound("e", args, fields)


class NBounds(Bounds):
    """ The northern outer bounds of a table. Used when growing a table. """
    @classmethod
    def from_factory_fields(cls, fields: list[F], **_) -> NBounds:
        w = BoundArgs(min, "x0", "x0")
        s = BoundArgs(min, "y0", "y0")
        e = BoundArgs(max, "x1", "x1")
        return super().from_factory_fields(fields, w=w, s=s, e=e)

    def update_missing_bound(self, fields: list[F]) -> None:
        """
        Update the eastern bound, which was not created using the datafields.
        """
        args: BoundArgs = BoundArgs(max, "y0", "y0")
        self._update_single_bound("n", args, fields)


class SBounds(Bounds):
    """ The southern outer bounds of a table. Used when growing a table. """
    @classmethod
    def from_factory_fields(cls, fields: list[F], **_) -> SBounds:
        n = BoundArgs(max, "y1", "y1")
        w = BoundArgs(min, "x0", "x0")
        e = BoundArgs(max, "x1", "x1")
        return super().from_factory_fields(fields, n=n, w=w, e=e)

    def update_missing_bound(self, fields: list[F]) -> None:
        """
        Update the eastern bound, which was not created using the datafields.
        """
        args: BoundArgs = BoundArgs(min, "y1", "y1")
        self._update_single_bound("s", args, fields)
