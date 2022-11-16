from test import P2GTestCase
from datastructures.pdftable.bbox import BBox, BBoxObject


class TestBBox(P2GTestCase):
    def setUp(self) -> None:
        self.bbox1 = BBox(5, 10, 10, 15)
        self.bbox2 = BBox(10, 15, 15, 20)
        self.bbox3 = BBox(0, 0, 30, 30)

    def test_from_char(self) -> None:
        ...

    def test_size(self) -> None:
        ...

    def test_is_valid(self) -> None:
        ...

    def test_copy(self) -> None:
        ...

    def test_contains_vertical(self) -> None:
        self.assertFalse(self.bbox1.contains_vertical(self.bbox2))
        self.assertFalse(self.bbox2.contains_vertical(self.bbox1))

    def test_contains_horizontal(self) -> None:
        ...

    def test_contains(self) -> None:
        self.assertTrue(self.bbox3.contains(self.bbox1))
        self.assertTrue(self.bbox3.contains(self.bbox2))
        self.assertTrue(self.bbox3.contains(self.bbox3))
        self.assertFalse(self.bbox1.contains(self.bbox2))
        self.assertFalse(self.bbox2.contains(self.bbox1))

    def test_merge(self) -> None:
        self.bbox1.merge(self.bbox2)
        self.assertEqual(self.bbox1.x0, 5)
        self.assertEqual(self.bbox1.y0, 10)
        self.assertEqual(self.bbox1.x1, 15)
        self.assertEqual(self.bbox1.y1, 20)

    def test__contains(self) -> None:
        ...

    def test_y_distance(self) -> None:
        self.assertEqual(0, self.bbox1.y_distance(self.bbox1))
        self.assertEqual(0, self.bbox1.y_distance(self.bbox2))
        self.assertEqual(10, self.bbox1.y_distance(self.bbox3))
        self.assertEqual(10, self.bbox2.y_distance(self.bbox3))

    def test_is_next_to(self) -> None:
        ...


class TestBBoxObject(P2GTestCase):
    def setUp(self) -> None:
        self.obj1 = BBoxObject()
        self.obj2 = BBoxObject(BBox(5, 10, 10, 20))

    def test_merge(self) -> None:
        ...

    def test__set_bbox_from_list(self) -> None:
        ...

    def test_is_next_to(self) -> None:
        ...