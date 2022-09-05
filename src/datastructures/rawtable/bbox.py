from __future__ import annotations

from operator import attrgetter

from p2g_types import Char


class BBox:
    """ Bounding box. Represented as (x0, y0, x1, y1).

    Origin is the upper left corner. First two coordinates represent the
    top-left corner of the bbox; the other two the bottom-right corner.
    """
    def __init__(
            self, x0: float = 0, y0: float = 0, x1: float = 1, y1: float = 1):
        self.x0 = x0
        self.y0 = y0
        self.x1 = x1
        self.y1 = y1

    @staticmethod
    def from_char(char: Char) -> BBox:
        return BBox(char.x0, char.y0, char.x1, char.y1)

    @property
    def size(self) -> tuple[float, float]:
        return self.x1 - self.x0, self.y1 - self.y0

    @property
    def is_valid(self) -> bool:
        return self.x0 < self.x1 and self.y0 < self.y1 and self.size > (0, 0)

    def copy(self) -> BBox:
        return BBox(self.x0, self.y0, self.x1, self.y1)

    def contains_vertical(self, other: BBox):
        return self._contains(other, "x")

    def contains_horizontal(self, other: BBox):
        return self._contains(other, "y")

    def contains(self, other: BBox, strict: bool = False) -> bool:
        return (self.contains_vertical(other) and
                self.contains_horizontal(other) and
                (not strict or self.is_valid and other.is_valid))

    def merge(self, other: BBox) -> None:
        self.x0 = min(self.x0, other.x0)
        self.y0 = min(self.y0, other.y0)
        self.x1 = max(self.x1, other.x1)
        self.y1 = max(self.y1, other.y1)

    def _contains(self, other, axis) -> bool:
        def _get(cls, bound) -> float:
            if bound == "lower":
                return getattr(cls, f"{axis}0")
            elif bound == "upper":
                return getattr(cls, f"{axis}1")

        lower, upper = _get(self, "lower"), _get(self, "upper")
        other_lower, other_upper = _get(other, "lower"), _get(other, "upper")

        return lower <= other_lower <= upper and lower <= other_upper <= upper

    def y_distance(self, other: BBox) -> float:
        """ Return the absolute distance of self to other on axis. """
        return min([abs(self.y0 - other.y0),
                    abs(self.y0 - other.y1),
                    abs(self.y1 - other.y0),
                    abs(self.y1 - other.y1)])

    def x_is_close(self, other) -> bool:
        lower, upper = sorted((self, other), key=attrgetter("x0"))
        return abs(upper.x0 - lower.x1) <= 0.01

    def __repr__(self) -> str:
        return f"BBox(x0={self.x0}, y0={self.y0}, x1={self.x1}, y1={self.y1})"


class BBoxObject:
    """ Baseclass for objects which have a bbox. """

    def __init__(self, bbox: BBox | None = None) -> None:
        self.bbox = bbox

    @property
    def bbox(self) -> BBox:
        return self._bbox

    @bbox.setter
    def bbox(self, bbox: BBox | None) -> None:
        self._bbox = BBox() if bbox is None else bbox.copy()

    def merge(self, other: BBoxObject | BBox):
        other_bbox = other if isinstance(other, BBox) else other.bbox
        self.bbox.x0 = min(self.bbox.x0, other_bbox.x0)
        self.bbox.y0 = min(self.bbox.y0, other_bbox.y0)
        self.bbox.x1 = max(self.bbox.x1, other_bbox.x1)
        self.bbox.y1 = max(self.bbox.y1, other_bbox.y1)

    def _set_bbox_from_list(self, bbox_objects: list[BBoxObject]):
        bbox = bbox_objects[0].bbox.copy() if bbox_objects else None
        for bbox_object in bbox_objects[1:]:
            bbox.merge(bbox_object.bbox)

        self.bbox = bbox

    def x_is_close(self, other: BBoxObject) -> bool:
        return self.bbox.x_is_close(other.bbox)
