from __future__ import annotations

from _operator import attrgetter
from typing import Callable, cast, Iterable, NamedTuple, TypeVar

from pdf2gtfs.datastructures.pdftable.bbox import BBox
from pdf2gtfs.datastructures.table.fields import F, TableField


B = TypeVar("B", bound="Bounds")
BoundArgs = NamedTuple("BoundArgs", [("func", Callable[[Iterable[F]], F]),
                                     ("bbox_attr", str),
                                     ("return_attr", str)])


class Bounds:
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
        return self._n

    @n.setter
    def n(self, value: float | None) -> None:
        self._n = value
        self._update_vbox()

    @property
    def s(self) -> float | None:
        return self._s

    @s.setter
    def s(self, value: float | None) -> None:
        self._s = value
        self._update_vbox()

    @property
    def w(self) -> float | None:
        return self._w

    @w.setter
    def w(self, value: float | None) -> None:
        self._w = value
        self._update_hbox()

    @property
    def e(self) -> float | None:
        return self._e

    @e.setter
    def e(self, value: float | None) -> None:
        self._e = value
        self._update_hbox()

    @property
    def hbox(self) -> BBox | None:
        return self._hbox

    @property
    def vbox(self) -> BBox | None:
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

    def within_bounds(self, obj: TableField) -> bool:
        bbox = obj.bbox
        return self._within_h_bounds(bbox) and self._within_v_bounds(bbox)

    def expand(self, other: B) -> None:
        """ Update the coordinates to the ones of other if they exist. """
        comp = {"n": "__le__", "s": "__ge__",
                "w": "__le__", "e": "__ge__"}
        for direction in ["n", "w", "s", "e"]:
            new_value = getattr(other, direction)
            if new_value is None:
                continue
            old_value = getattr(self, direction)
            if old_value is not None:
                if getattr(old_value, comp[direction])(new_value):
                    continue
            setattr(self, direction, new_value)

    @staticmethod
    def get_bound_from_fields(args: BoundArgs | None, fields: list[TableField]
                              ) -> float | None:
        if args is None:
            return None
        func, bbox_coordinate, return_coordinate = args
        field = func(fields, key=attrgetter(f"bbox.{bbox_coordinate}"))
        return cast(float, attrgetter(f"bbox.{return_coordinate}")(field))

    @classmethod
    def from_factory_fields(cls, fields: list[F], **kwargs) -> B:
        bounds = {d: cls.get_bound_from_fields(kwargs.get(d), fields)
                  for d in ["n", "w", "s", "e"]}
        return cls(**bounds)

    def _update_single_bound(
            self, which: str, args: BoundArgs, fields: list[TableField]
            ) -> None:
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


class WBounds(Bounds):
    @classmethod
    def from_factory_fields(cls, fields: list[F], **_) -> WBounds:
        kwargs = {"n": BoundArgs(min, "y0", "y0"),
                  "s": BoundArgs(max, "y1", "y1"),
                  "e": BoundArgs(min, "x0", "x0")}
        return super().from_factory_fields(fields, **kwargs)

    def update_missing_bound(self, fields: list[F]) -> None:
        """
        Update the western bound, which was not created using the datafields.
        """
        args: BoundArgs = BoundArgs(max, "x0", "x0")
        self._update_single_bound("w", args, fields)


class EBounds(Bounds):
    @classmethod
    def from_factory_fields(cls, fields: list[F], **_) -> EBounds:
        kwargs = {"n": BoundArgs(min, "y0", "y0"),
                  "s": BoundArgs(max, "y1", "y1"),
                  "w": BoundArgs(max, "x1", "x1")}
        return super().from_factory_fields(fields, **kwargs)

    def update_missing_bound(self, fields: list[F]) -> None:
        """
        Update the eastern bound, which was not created using the datafields.
        """
        args: BoundArgs = BoundArgs(min, "x1", "x1")
        self._update_single_bound("e", args, fields)


class NBounds(Bounds):
    @classmethod
    def from_factory_fields(cls, fields: list[F], **_) -> NBounds:
        kwargs = {"w": BoundArgs(min, "x0", "x0"),
                  "s": BoundArgs(min, "y0", "y0"),
                  "e": BoundArgs(max, "x1", "x1")}
        return super().from_factory_fields(fields, **kwargs)

    def update_missing_bound(self, fields: list[TableField]) -> None:
        """
        Update the eastern bound, which was not created using the datafields.
        """
        args: BoundArgs = BoundArgs(max, "y0", "y0")
        self._update_single_bound("n", args, fields)


class SBounds(Bounds):
    @classmethod
    def from_factory_fields(cls, fields: list[F], **_) -> SBounds:
        kwargs = {"n": BoundArgs(max, "y1", "y1"),
                  "w": BoundArgs(min, "x0", "x0"),
                  "e": BoundArgs(max, "x1", "x1")}
        return super().from_factory_fields(fields, **kwargs)

    def update_missing_bound(self, fields: list[F]) -> None:
        """
        Update the eastern bound, which was not created using the datafields.
        """
        args: BoundArgs = BoundArgs(min, "y1", "y1")
        self._update_single_bound("s", args, fields)
