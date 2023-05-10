from unittest import TestCase

from more_itertools import distinct_permutations
from pdfminer.pdffont import PDFFont

from pdf2gtfs.config import Config
from pdf2gtfs.datastructures.pdftable.bbox import BBox
from pdf2gtfs.datastructures.table.direction import E, H, N, S, V, W
from pdf2gtfs.datastructures.table.fields import EmptyField, Field
from pdf2gtfs.datastructures.table.fieldtype import ABS_FALLBACK, T
from pdf2gtfs.datastructures.table.quadlinkedlist import QuadLinkedList


class TestField(TestCase):
    def test_duplicate(self) -> None:
        font = PDFFont({}, {})
        fontsize = 5.3321
        f1 = Field("field1", None, font, font.fontname, fontsize)
        _ = QuadLinkedList(f1, f1)
        self.assertIsNotNone(f1.qll)
        f2 = f1.duplicate()
        self.assertNotEqual(id(f1), id(f2))
        self.assertEqual(f1.text, f2.text)
        self.assertEqual(f1.bbox, f2.bbox)
        self.assertEqual(f1.font, f2.font)
        self.assertEqual(f1.fontname, f2.fontname)
        self.assertEqual(f1.fontsize, f2.fontsize)
        # The table and type are not duplicated.
        self.assertIsNone(f2.qll)
        self.assertNotEqual(f1.qll, f2.qll)
        self.assertNotEqual(f1.type, f2.type)

    def test_get_type(self) -> None:
        f = Field("test", None)
        self.assertDictEqual({}, f.type.possible_types)
        t = f.get_type()
        self.assertListEqual(list(f.type.possible_types),
                             ABS_FALLBACK + [T.Other])
        self.assertEqual(T.Other, t)

        Config.time_format = "%H:%M"
        f2 = Field("13:37", None)
        self.assertEqual(T.Data, f2.get_type())
        self.assertListEqual([T.Data, T.LegendIdent, T.Other],
                             list(f2.type.possible_types))

    def test_has_type(self) -> None:
        f = Field("test", None)
        possible_types = [T.Other, T.Stop, T.EntryAnnotValue]
        f.type.possible_types = {t: 0.33 for t in possible_types}

        p = distinct_permutations(possible_types)
        for i, types in enumerate(p):
            with self.subTest(types=types):
                self.assertTrue(f.has_type(*types))
        p = [t for t in T if t not in possible_types]
        for i, type_ in enumerate(p):
            with self.subTest(types=type_):
                self.assertFalse(f.has_type(type_))

    def test_get_neighbors(self) -> None:
        fc = Field("center")
        fl = Field("left")
        fr = Field("right")
        fa = Field("above")
        fb = Field("below")
        self.assertListEqual([], fc.get_neighbors())
        self.assertListEqual([None, None, None, None],
                             fc.get_neighbors(allow_none=True))
        fc.set_neighbor(W, fl)
        self.assertListEqual([fl], fc.get_neighbors())
        self.assertListEqual([None, fl, None, None],
                             fc.get_neighbors(allow_none=True))
        fc.set_neighbor(E, fr)
        self.assertListEqual([fl, fr], fc.get_neighbors())
        self.assertListEqual([None, fl, None, fr],
                             fc.get_neighbors(allow_none=True))
        fc.set_neighbor(N, fa)
        self.assertListEqual([fa, fl, fr], fc.get_neighbors())
        self.assertListEqual([fa, fl, None, fr],
                             fc.get_neighbors(allow_none=True))
        fc.set_neighbor(S, fb)
        self.assertListEqual([fa, fl, fb, fr], fc.get_neighbors())
        self.assertListEqual([fa, fl, fb, fr],
                             fc.get_neighbors(allow_none=True))
        # Subset of directions.
        self.assertListEqual([fa, fr],
                             fc.get_neighbors(directions=[N, E]))
        fc.set_neighbor(N, None)
        # Subset of directions with no neighbor in the given direction.
        self.assertListEqual([fr],
                             fc.get_neighbors(directions=[N, E]))
        self.assertListEqual([None, fr],
                             fc.get_neighbors(allow_none=True,
                                              directions=[N, E]))
        fc.set_neighbor(N, fa)

        # Empty fields.
        fe = EmptyField()
        fc.set_neighbor(E, fe)
        self.assertListEqual([fa, fl, fb, fe], fc.get_neighbors())
        self.assertListEqual([fa, fl, fb, fr],
                             fc.get_neighbors(allow_empty=False))

    def test_is_overlap(self) -> None:
        bbox1 = BBox(3, 10, 6, 11)
        bbox2 = BBox(6, 11, 7, 12)
        bbox3 = BBox(1, 11, 4, 12)
        f1 = Field("f1", bbox1)
        f2 = Field("f2", bbox2)
        f3 = Field("f3", bbox3)
        # Each field overlaps with itself.
        for i, f in enumerate((f1, f2, f3)):
            with self.subTest(i=i):
                self.assertTrue(f.is_overlap(V, f, 1.0))
                self.assertTrue(f.is_overlap(H, f, 1.0))

        self.assertFalse(f1.is_overlap(V, f2, 0.8))
        self.assertFalse(f1.is_overlap(H, f2, 0.8))
        self.assertFalse(f1.is_overlap(V, f3, 0.8))
        self.assertFalse(f1.is_overlap(H, f3, 0.8))
        # Same y coordinates.
        self.assertTrue(f2.is_overlap(V, f3, 1.))
        self.assertTrue(f3.is_overlap(V, f2, 1.))
        # Absolute overlap is 1/3.
        self.assertTrue(f1.is_overlap(H, f3, 0.33))

    def test_any_overlap(self) -> None:
        # Vertical overlap.
        bbox1 = BBox(3, 10, 6, 11)
        bbox2 = BBox(6, 11, 7, 12)
        bbox3 = BBox(1, 11, 4, 12)
        f1 = Field("f1", bbox1)
        f2 = Field("f2", bbox2)
        f3 = Field("f3", bbox3)
        self.assertFalse(f1.any_overlap(V, f2))
        self.assertFalse(f1.any_overlap(H, f2))
        self.assertFalse(f1.any_overlap(V, f3))
        self.assertTrue(f1.any_overlap(H, f3))
        self.assertTrue(f2.any_overlap(V, f3))
        self.assertFalse(f2.any_overlap(H, f3))

    def test_merge(self) -> None:
        bbox1 = BBox(3, 10, 6, 11)
        bbox2 = BBox(6, 11, 7, 12)
        bbox3 = BBox(33, 13, 34, 14)
        # Using .copy() here, to reuse the unchanged bboxes below.
        f1 = Field("f1", bbox1.copy())
        f2 = Field("f2", bbox2.copy())
        f3 = Field("f3", bbox3.copy())
        f1.merge(f2, merge_char=" merged ")
        self.assertEqual("f1 merged f2", f1.text)
        self.assertTrue(f1.bbox.is_h_overlap(bbox1, 1.))
        self.assertTrue(f1.bbox.is_v_overlap(bbox1, 1.))
        self.assertTrue(f1.bbox.is_h_overlap(bbox2, 1.))
        self.assertTrue(f1.bbox.is_v_overlap(bbox2, 1.))
        self.assertFalse(f1.bbox.is_h_overlap(bbox3, 0.1))
        self.assertFalse(f1.bbox.is_v_overlap(bbox3, 0.1))
        f1.merge(f3, merge_char=",")
        self.assertEqual("f1 merged f2,f3", f1.text)
        self.assertTrue(f1.bbox.is_h_overlap(bbox3, 1.))
        self.assertTrue(f1.bbox.is_v_overlap(bbox3, 1.))
