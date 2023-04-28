from unittest import TestCase

from pdf2gtfs.datastructures.table.direction import D, H, V


class TestDirections(TestCase):
    def test_attr(self) -> None:
        for d in D:
            with self.subTest(orientation=d.name):
                self.assertFalse(d.attr.startswith("_"))
                self.assertTrue(d.p_attr.startswith("_"))
                self.assertEqual(d.attr, d.p_attr[1:])

    def test_end(self) -> None:
        for d in D:
            with self.subTest(orientation=d.name):
                self.assertFalse(d.end.startswith("_"))
                self.assertTrue(d.p_end.startswith("_"))
                self.assertEqual(d.end, d.p_end[1:])

    def test_opposite(self) -> None:
        for d in D:
            with self.subTest(orientation=d.name):
                self.assertEqual(d, d.opposite.opposite)

    def test_default_orientation(self) -> None:
        for d in D[:2]:
            with self.subTest(orientation=d.name):
                self.assertEqual(d, d.default_orientation.lower)
                self.assertEqual(d.opposite, d.default_orientation.upper)
        for d in D[2:]:
            with self.subTest(orientation=d.name):
                self.assertEqual(d, d.default_orientation.upper)
                self.assertEqual(d.opposite, d.default_orientation.lower)


class TestOrientations(TestCase):
    def test_normal(self) -> None:
        for o in [V, H]:
            with self.subTest(orientation=o.name):
                self.assertEqual(o, o.normal.normal)

    def test_lower_and_upper(self) -> None:
        for o in [V, H]:
            with self.subTest(orientation=o.name):
                self.assertLess(D.index(o.lower), 2)
                self.assertGreaterEqual(D.index(o.upper), 2)
                self.assertEqual(o, o.lower.default_orientation)
                self.assertEqual(o, o.upper.default_orientation)
