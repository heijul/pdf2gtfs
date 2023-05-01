from unittest import TestCase

from more_itertools import distinct_permutations
from pdfminer.pdffont import PDFFont

from pdf2gtfs.config import Config
from pdf2gtfs.datastructures.table.fields import Field
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
        self.assertListEqual(list(f.type.possible_types), ABS_FALLBACK)
        self.assertEqual(T.Other, t)

        Config.time_format = "%H:%M"
        f2 = Field("13:37", None)
        self.assertEqual(T.Data, f2.get_type())
        self.assertListEqual([T.Stop, T.Other], list(f2.type.possible_types))

    def test_has_type(self) -> None:
        f = Field("test", None)
        possible_types = [T.Other, T.Stop, T.EntryAnnotValue]
        f.type.possible_types = {t: 0.33 for t in possible_types}

        p = distinct_permutations(possible_types)
        for i, types in enumerate(p):
            with self.subTest(types=types):
                self.assertTrue(f.has_type(*types))
        p = distinct_permutations([t for t in T if t not in possible_types])
        for i, types in enumerate(p):
            with self.subTest(types=types):
                self.assertFalse(f.has_type(*types))

