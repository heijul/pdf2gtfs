from config import Config
from datastructures.pdftable import Char
from test import P2GTestCase
from datastructures.pdftable.bbox import BBox, BBoxObject


class TestBBox(P2GTestCase):
    def setUp(self) -> None:
        self.bbox1 = BBox(5, 10, 10, 15)
        self.bbox2 = BBox(10, 15, 15, 20)
        self.bbox3 = BBox(0, 0, 30, 30)

    def test_from_char(self) -> None:
        c = Char(42.3, 44.4, 20.9, 28.9, "A")
        bbox = BBox.from_char(c)
        self.assertEqual(42.3, bbox.x0)
        self.assertEqual(44.4, bbox.x1)
        self.assertEqual(20.9, bbox.y0)
        self.assertEqual(28.9, bbox.y1)

    def test_size(self) -> None:
        self.assertEqual(self.bbox1.size, self.bbox2.size)
        self.assertEqual((5, 5), self.bbox1.size)
        self.assertEqual((30, 30), self.bbox3.size)
        bbox = BBox(4, 8, 12, 18)
        self.assertEqual((8, 10), bbox.size)

    def test_is_valid(self) -> None:
        self.assertTrue(self.bbox1.is_valid)
        self.assertTrue(self.bbox2.is_valid)
        self.assertTrue(self.bbox3.is_valid)
        bbox4 = BBox(0, 10, 2, 8)
        self.assertFalse(bbox4.is_valid)

    def test_copy(self) -> None:
        # Need to use repr cause there is not __eq__
        self.assertEqual(repr(self.bbox1), repr(self.bbox1.copy()))
        self.assertEqual(repr(self.bbox2), repr(self.bbox2.copy()))
        self.assertEqual(repr(self.bbox3), repr(self.bbox3.copy()))

    def test_contains_vertical(self) -> None:
        self.assertFalse(self.bbox1.contains_vertical(self.bbox2))
        self.assertFalse(self.bbox2.contains_vertical(self.bbox1))
        self.assertTrue(self.bbox1.contains_vertical(self.bbox1))
        self.assertTrue(self.bbox2.contains_vertical(self.bbox2))

    def test_merge(self) -> None:
        self.bbox1.merge(self.bbox2)
        self.assertEqual(self.bbox1.x0, 5)
        self.assertEqual(self.bbox1.y0, 10)
        self.assertEqual(self.bbox1.x1, 15)
        self.assertEqual(self.bbox1.y1, 20)

    def test_y_distance(self) -> None:
        self.assertEqual(0, self.bbox1.y_distance(self.bbox1))
        self.assertEqual(0, self.bbox1.y_distance(self.bbox2))
        self.assertEqual(10, self.bbox1.y_distance(self.bbox3))
        self.assertEqual(10, self.bbox2.y_distance(self.bbox3))

    def test_is_next_to(self) -> None:
        bbox1 = BBox(140.3, 0, 144.12, 1)
        bbox2 = BBox(145.2, 1, 148.13, 1)
        bbox3 = BBox(100.1, 0, 139.78, 1)
        Config.max_char_distance = 3.
        self.assertTrue(bbox1.is_next_to(bbox2))
        self.assertTrue(bbox3.is_next_to(bbox1))
        self.assertFalse(bbox3.is_next_to(bbox2))
        Config.max_char_distance = 6.
        self.assertTrue(bbox3.is_next_to(bbox2))
        self.assertEqual(bbox1.is_next_to(bbox2), bbox2.is_next_to(bbox1))
        self.assertEqual(bbox1.is_next_to(bbox3), bbox3.is_next_to(bbox1))
        self.assertEqual(bbox2.is_next_to(bbox3), bbox3.is_next_to(bbox2))


class TestBBoxObject(P2GTestCase):
    def setUp(self) -> None:
        self.obj1 = BBoxObject()
        self.obj2 = BBoxObject(BBox(5, 10, 10, 20))

    def test_merge(self) -> None:
        bbox1 = self.obj1.bbox.copy()
        bbox2 = self.obj2.bbox.copy()

        self.obj1.merge(self.obj2)
        bbox1.merge(bbox2)
        self.assertEqual(repr(bbox1), repr(self.obj1.bbox))

    def test__set_bbox_from_list(self) -> None:
        bboxes = []
        for i in range(1, 6):
            bboxes.append(BBoxObject(BBox(i * 5, i * 3, i * 8, i * 5)))
        self.assertEqual((1, 1), self.obj1.bbox.size)
        self.obj1._set_bbox_from_list(bboxes)
        self.assertEqual((35, 22), self.obj1.bbox.size)
        self.assertEqual(5, self.obj1.bbox.x0)
        self.assertEqual(3, self.obj1.bbox.y0)
        self.assertEqual(40, self.obj1.bbox.x1)
        self.assertEqual(25, self.obj1.bbox.y1)
