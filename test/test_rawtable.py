from unittest import TestCase

from datastructures.rawtable.bbox import BBox


class TestBBox(TestCase):
    def setUp(self) -> None:
        self.bbox1 = BBox(0, 10, 0, 10)
        self.bbox2 = BBox(10, 20, 20, 30)

    def test_merge(self):
        self.bbox1.merge(self.bbox2)
        self.assertEqual(self.bbox1.x0, 0)
        self.assertEqual(self.bbox1.y0, 10)
        self.assertEqual(self.bbox1.x1, 20)
        self.assertEqual(self.bbox1.y1, 30)

    def test_contains(self):
        pass
