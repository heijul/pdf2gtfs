from typing import Iterator
from unittest import TestCase

from pdf2gtfs.datastructures.table.bounds import Bounds


class TestBounds(TestCase):
    def test_vertical_setter(self) -> None:
        b1 = Bounds(None, None, None, None)
        b2 = Bounds(None, None, None, None)
        b1.n = 42
        b2.s = 35
        self.assertIsNone(b1.vbox)
        self.assertIsNone(b2.vbox)
        b1.s = 64
        b2.n = 12
        self.assertIsNotNone(b1.vbox)
        self.assertEqual(42, b1.vbox.y0)
        self.assertEqual(64, b1.vbox.y1)
        self.assertIsNotNone(b2.vbox)
        self.assertEqual(12, b2.vbox.y0)
        self.assertEqual(35, b2.vbox.y1)

    def test_horizontal_setter(self) -> None:
        b1 = Bounds(None, None, None, None)
        b2 = Bounds(None, None, None, None)
        b1.w = 42
        b2.e = 35
        self.assertIsNone(b1.hbox)
        self.assertIsNone(b2.hbox)
        b1.e = 64
        b2.w = 12
        self.assertIsNotNone(b1.hbox)
        self.assertEqual(42, b1.hbox.x0)
        self.assertEqual(64, b1.hbox.x1)
        self.assertIsNotNone(b2.hbox)
        self.assertEqual(12, b2.hbox.x0)
        self.assertEqual(35, b2.hbox.x1)

    def test_within_v_bounds(self) -> None:
        b1 = Bounds(1.412, None, 5.321, None)
        # These are within bounds.
        wb1 = Bounds(1., None, 3., None)
        wb2 = Bounds(5., None, 5.3, None)
        within_bounds = [b1, wb1, wb2]
        for i, bound in enumerate(within_bounds):
            with self.subTest(i=i):
                self.assertTrue(b1._within_v_bounds(bound.vbox))
        # These are out of bounds.
        ob1 = Bounds(1., None, 1.5, None)
        ob2 = Bounds(5., None, 10., None)
        ob3 = Bounds(10., None, 12., None)
        outside_bounds = [ob1, ob2, ob3]
        for i, outside_bound in enumerate(outside_bounds):
            with self.subTest(i=i):
                self.assertFalse(b1._within_v_bounds(outside_bound.vbox))

        b1.n = None
        # Can not use b1.vbox here, as it is None.
        for i, bound in enumerate(within_bounds[1:]):
            with self.subTest(i=i):
                self.assertTrue(b1._within_v_bounds(bound.vbox))
        # No overlap percentage is required now, only coordinates are checked.
        self.assertTrue(b1._within_v_bounds(ob1.vbox))
        self.assertTrue(b1._within_v_bounds(ob2.vbox))
        # This is still out of bounds (to the right of b1)
        self.assertFalse(b1._within_v_bounds(ob3.vbox))

        b1.n = 1.412
        b1.s = None
        # Can not use b1.vbox here, as it is None.
        # Outside bounds are all within bounds now.
        for i, bound in enumerate(within_bounds[1:] + outside_bounds):
            with self.subTest(i=i):
                self.assertTrue(b1._within_v_bounds(bound.vbox))

        b1.n = None
        for i, bound in enumerate(within_bounds + outside_bounds):
            with self.subTest(i=i):
                self.assertTrue(b1._within_v_bounds(bound.vbox))

    def test_within_h_bounds(self) -> None:
        b1 = Bounds(None, 1.412, None, 5.321)
        # These are within bounds.
        wb1 = Bounds(None, 1., None, 3.)
        wb2 = Bounds(None, 5., None, 5.3)
        within_bounds = [b1, wb1, wb2]
        for i, bound in enumerate(within_bounds):
            with self.subTest(i=i):
                self.assertTrue(b1._within_h_bounds(bound.hbox))
        # These are out of bounds.
        ob1 = Bounds(None, 1., None, 1.5)
        ob2 = Bounds(None, 5., None, 10.)
        ob3 = Bounds(None, 10., None, 12.)
        outside_bounds = [ob1, ob2, ob3]
        for i, outside_bound in enumerate(outside_bounds):
            with self.subTest(i=i):
                self.assertFalse(b1._within_h_bounds(outside_bound.hbox))

        b1.w = None
        # Can not use b1.hbox here, as it is None.
        for i, bound in enumerate(within_bounds[1:]):
            with self.subTest(i=i):
                self.assertTrue(b1._within_h_bounds(bound.hbox))
        # No overlap percentage is required now, only coordinates are checked.
        self.assertTrue(b1._within_h_bounds(ob1.hbox))
        self.assertTrue(b1._within_h_bounds(ob2.hbox))
        # This is still out of bounds (to the right of b1)
        self.assertFalse(b1._within_h_bounds(ob3.hbox))

        b1.w = 1.412
        b1.e = None
        # Can not use b1.hbox here, as it is None.
        # Outside bounds are all within bounds now.
        for i, bound in enumerate(within_bounds[1:] + outside_bounds):
            with self.subTest(i=i):
                self.assertTrue(b1._within_h_bounds(bound.hbox))

        b1.w = None
        for i, bound in enumerate(within_bounds + outside_bounds):
            with self.subTest(i=i):
                self.assertTrue(b1._within_h_bounds(bound.hbox))


def create_bounds(num: int) -> Iterator[Bounds]:
    return (Bounds(None, None, None, None) for _ in range(num))
