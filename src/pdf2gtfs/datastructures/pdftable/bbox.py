""" Contains both the BBox, which is used to represent the position and size
of various pdf objects, and the BBoxObject, which is the base class for
objects using a BBox. """

from __future__ import annotations

from operator import attrgetter

from pdf2gtfs.config import Config
from pdf2gtfs.datastructures.pdftable import Char


class BBox:
    """ Bounding box. Represented as (x0, y0, x1, y1).

    Origin is the upper left corner. First two coordinates represent the
    top-left corner of the bbox, the last two the bottom-right corner.
    """

    def __init__(
            self, x0: float = 0, y0: float = 0, x1: float = 1, y1: float = 1):
        self.x0 = x0
        self.y0 = y0
        self.x1 = x1
        self.y1 = y1

    @staticmethod
    def from_char(char: Char) -> BBox:
        """ Return the bbox, given the specific char. """
        return BBox(char.x0, char.y0, char.x1, char.y1)

    @property
    def size(self) -> tuple[float, float]:
        """ Return the x and y size of the bbox in points. """
        return self.x1 - self.x0, self.y1 - self.y0

    @property
    def is_valid(self) -> bool:
        """ Returns True, if the coordinates are in the right order and
        if bbox has both x- and y-size, otherwise False. """
        return self.x0 < self.x1 and self.y0 < self.y1 and self.size > (0, 0)

    @staticmethod
    def from_bboxes(bboxes: list[BBox]) -> BBox:
        """ Create a new bbox from the given bboxes.

        :param bboxes: The bboxes to construct the bbox from.
        :return: A bbox, that contains all other bboxes.
        """
        bbox = bboxes[0].copy()
        bbox.x0 = min(map(attrgetter("x0"), bboxes))
        bbox.y0 = min(map(attrgetter("y0"), bboxes))
        bbox.x1 = max(map(attrgetter("x1"), bboxes))
        bbox.y1 = max(map(attrgetter("y1"), bboxes))
        return bbox

    def copy(self) -> BBox:
        """ Return a new BBox with the same coordinates. """
        return BBox(self.x0, self.y0, self.x1, self.y1)

    def contains_vertical(self, bbox: BBox):
        """ Returns, whether other's x coordinates lie within self's. """
        return self.x0 <= bbox.x0 <= self.x1 and self.x0 <= bbox.x1 <= self.x1

    def merge(self, other: BBox) -> BBox:
        """ Merges other with self (inplace), such that:
        merged.contains(self) == merged.contains(other) == True,
        if merged = self.copy().merge(other). """
        self.x0 = min(self.x0, other.x0)
        self.y0 = min(self.y0, other.y0)
        self.x1 = max(self.x1, other.x1)
        self.y1 = max(self.y1, other.y1)
        return self

    def y_distance(self, other: BBox) -> float:
        """ Return the absolute distance of self to other on axis. """
        return min([abs(self.y0 - other.y0),
                    abs(self.y0 - other.y1),
                    abs(self.y1 - other.y0),
                    abs(self.y1 - other.y1)])

    def is_next_to(self, other) -> bool:
        """ Checks if the two bboxes are touching or close to each other.

        Completely ignores the y components.
        """
        left, right = sorted((self, other), key=attrgetter("x0"))
        # Overlapping bboxes are always next to each other.
        if right.x0 <= left.x1:
            return True
        return abs(right.x0 - left.x1) <= Config.max_char_distance

    def __eq__(self, other: BBox):
        return (self.x0 == other.x0 and self.x1 == other.x1
                and self.y0 == other.y0 and self.y1 == other.y1)

    def __repr__(self) -> str:
        return f"BBox(x0={self.x0}, y0={self.y0}, x1={self.x1}, y1={self.y1})"

    def _overlap(self, other: BBox | BBoxObject, d: str) -> float:
        """ Return how much self and other overlap, in points. """
        if not isinstance(other, BBox):
            other = other.bbox
        assert d in ["x", "y"]
        # Sort the two objects by the left/upper side, to have fewer cases.
        one, two = sorted((self, other), key=attrgetter(f"{d}0"))

        # The left/top of the righter/lower object is greater than the
        #  right/bottom side of the lefter/upper object.
        if getattr(one, f"{d}1") <= getattr(two, f"{d}0"):
            return 0
        # The righter/lower object is completely contained in the lefter/upper.
        if getattr(one, f"{d}1") >= getattr(two, f"{d}1"):
            return two.size[0] if d == "x" else two.size[1]
        # Need to actually calculate the overlap.
        return abs(getattr(one, f"{d}1") - getattr(two, f"{d}0"))

    def h_overlap(self, other: BBox | BBoxObject) -> float:
        """ Return how much self and other overlap horizontally, in pixel. """
        return self._overlap(other, "x")

    def is_h_overlap(self, other: BBox | BBoxObject,
                     relative_amount: float = None) -> bool:
        if relative_amount is None:
            relative_amount = Config.min_cell_overlap
        max_overlap = min((self.size[0], other.size[0]))
        return self.h_overlap(other) >= relative_amount * max_overlap

    def v_overlap(self, other: BBox | BBoxObject) -> float:
        """ Return how much self and other overlap vertically, in pixel. """
        return self._overlap(other, "y")

    def is_v_overlap(self, other: BBox | BBoxObject,
                     relative_amount: float = None) -> bool:
        if relative_amount is None:
            relative_amount = Config.min_cell_overlap
        max_overlap = min((self.size[1], other.size[1]))
        return self.v_overlap(other) >= relative_amount * max_overlap

    def is_overlap(self, orientation: str = "v", *args, **kwargs) -> bool:
        # TODO NOW: Use Orientation instead of str
        assert orientation in "vh"
        if orientation == "v":
            return self.is_v_overlap(*args, **kwargs)
        return self.is_h_overlap(*args, **kwargs)

    def __hash__(self) -> int:
        return hash(f"{self.x0},{self.y0},{self.x1},{self.y1}")


class BBoxObject:
    """ Baseclass for objects which have a bbox. """

    def __init__(self, bbox: BBox | None = None) -> None:
        self._bbox = BBox() if bbox is None else bbox.copy()

    @property
    def bbox(self) -> BBox:
        """ The bbox , that contains the object. """
        return self._bbox

    @bbox.setter
    def bbox(self, bbox: BBox | None) -> None:
        self._bbox = BBox() if bbox is None else bbox.copy()

    def _set_bbox_from_list(self, bbox_objects: list[BBoxObject]):
        bbox = bbox_objects[0].bbox.copy() if bbox_objects else None
        for bbox_object in bbox_objects[1:]:
            bbox.merge(bbox_object.bbox)

        self.bbox = bbox

    def is_next_to(self, other: BBoxObject) -> bool:
        """ Checks if the objects' bboxes are next to each other. """
        return self.bbox.is_next_to(other.bbox)
