from unittest import TestCase

from datastructures.rawtable.bbox import BBox


class TestBBox(TestCase):
    def setUp(self) -> None:
        self.bbox1 = BBox(5, 10, 10, 15)
        self.bbox2 = BBox(10, 15, 15, 20)
        self.bbox3 = BBox(0, 0, 30, 30)

    def test_merge(self):
        self.bbox1.merge(self.bbox2)
        self.assertEqual(self.bbox1.x0, 5)
        self.assertEqual(self.bbox1.y0, 10)
        self.assertEqual(self.bbox1.x1, 15)
        self.assertEqual(self.bbox1.y1, 20)

    def test_contains(self):
        self.assertTrue(self.bbox3.contains(self.bbox1))
        self.assertTrue(self.bbox3.contains(self.bbox2))
        self.assertTrue(self.bbox3.contains(self.bbox3))
        self.assertFalse(self.bbox1.contains(self.bbox2))
        self.assertFalse(self.bbox2.contains(self.bbox1))

    def test_contains_vertical(self):
        self.assertFalse(self.bbox1.contains_vertical(self.bbox2))
        self.assertFalse(self.bbox2.contains_vertical(self.bbox1))

    def test_distance(self):
        self.skipTest("Not implemented yet...")
