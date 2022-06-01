from __future__ import annotations

import pandas as pd


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
    def from_series(series: pd.Series) -> BBox:
        """ Creates a bbox from a series.

        If series has a top attribute, the series' coordinate origin will
        be recognized as the bottom-left corner and will be converted.
        """

        y0 = series.y0
        y1 = series.y1
        top = getattr(series, "top", None)
        if top is not None:
            height = y1 - y0
            y1 = top + height
            y0 = top
        return BBox(series.x0, y0, series.x1, y1)

    @property
    def size(self):
        return self.x1 - self.x0, self.y1 - self.y0

    @property
    def is_valid(self):
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

    def set(self, coordinate: str, value: float) -> None:
        assert coordinate in ["x0", "y0", "x1", "y1"]
        setattr(self, coordinate, value)

    def _contains(self, other, axis):
        def _get(cls, bound):
            if bound == "lower":
                return getattr(cls, f"{axis}0")
            elif bound == "upper":
                return getattr(cls, f"{axis}1")

        lower, upper = _get(self, "lower"), _get(self, "upper")
        other_lower, other_upper = _get(other, "lower"), _get(other, "upper")

        return lower <= other_lower <= upper and lower <= other_upper <= upper

    def distance(self, other: BBox, axis: str | None = None) -> float:
        """ Return the absolute distance of self to other on the given axis.

        If no axis is given return the minimum distance on either axis."""
        assert axis in ["x", "y", None]

        if axis is not None:
            return self._distance(other, axis)
        return min([self._distance(other, "x"), self._distance(other, "y")])

    def _distance(self, other: BBox, axis: str) -> float:
        """ Returns the minimal distance between two bboxes on the given axis.

        If one bbox is contained by the other, return the minimal distance
        of the contained bbox to the others' bounds.
        """
        self_0 = getattr(self, f"{axis}0")
        self_1 = getattr(self, f"{axis}1")
        other_0 = getattr(other, f"{axis}0")
        other_1 = getattr(other, f"{axis}1")

        return min([abs(self_0 - other_0),
                    abs(self_0 - other_1),
                    abs(self_1 - other_0),
                    abs(self_1 - other_1)])

    def __repr__(self):
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
