from unittest import TestCase

from more_itertools import distinct_permutations, peekable
from pdfminer.pdffont import PDFFont

from pdf2gtfs.config import Config
from pdf2gtfs.datastructures.pdftable.bbox import BBox
from pdf2gtfs.datastructures.table.direction import Direction, E, H, N, S, V, W
from pdf2gtfs.datastructures.table.cell import EmptyCell, Cell
from pdf2gtfs.datastructures.table.celltype import ABS_FALLBACK, T
from pdf2gtfs.datastructures.table.table import Table


class TestField(TestCase):
    def test_duplicate(self) -> None:
        font = PDFFont({}, {})
        fontsize = 5.3321
        f1 = Cell("cell1", None, font, font.fontname, fontsize)
        _ = Table(f1, f1)
        self.assertIsNotNone(f1.table)
        f2 = f1.duplicate()
        self.assertNotEqual(id(f1), id(f2))
        self.assertEqual(f1.text, f2.text)
        self.assertEqual(f1.bbox, f2.bbox)
        self.assertEqual(f1.font, f2.font)
        self.assertEqual(f1.fontname, f2.fontname)
        self.assertEqual(f1.fontsize, f2.fontsize)
        # The table and type are not duplicated.
        self.assertIsNone(f2.table)
        self.assertNotEqual(f1.table, f2.table)
        self.assertNotEqual(f1.type, f2.type)

    def test_get_type(self) -> None:
        f = Cell("test", None)
        self.assertDictEqual({}, f.type.possible_types)
        t = f.get_type()
        self.assertListEqual(list(f.type.possible_types),
                             ABS_FALLBACK + [T.Other])
        self.assertEqual(T.Other, t)

        Config.time_format = "%H:%M"
        f2 = Cell("13:37", None)
        self.assertEqual(T.Time, f2.get_type())
        self.assertListEqual([T.Time, T.LegendIdent, T.Other],
                             list(f2.type.possible_types))

    def test_has_type(self) -> None:
        f = Cell("test", None)
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
        fc = Cell("center")
        fl = Cell("left")
        fr = Cell("right")
        fa = Cell("above")
        fb = Cell("below")
        self.assertListEqual([], fc.get_neighbors())
        self.assertListEqual([None, None, None, None],
                             fc.get_neighbors(allow_none=True))
        fc.update_neighbor(W, fl)
        self.assertListEqual([fl], fc.get_neighbors())
        self.assertListEqual([None, fl, None, None],
                             fc.get_neighbors(allow_none=True))
        fc.update_neighbor(E, fr)
        self.assertListEqual([fl, fr], fc.get_neighbors())
        self.assertListEqual([None, fl, None, fr],
                             fc.get_neighbors(allow_none=True))
        fc.update_neighbor(N, fa)
        self.assertListEqual([fa, fl, fr], fc.get_neighbors())
        self.assertListEqual([fa, fl, None, fr],
                             fc.get_neighbors(allow_none=True))
        fc.update_neighbor(S, fb)
        self.assertListEqual([fa, fl, fb, fr], fc.get_neighbors())
        self.assertListEqual([fa, fl, fb, fr],
                             fc.get_neighbors(allow_none=True))
        # Subset of directions.
        self.assertListEqual([fa, fr],
                             fc.get_neighbors(directions=[N, E]))
        fc.update_neighbor(N, None)
        # Subset of directions with no neighbor in the given direction.
        self.assertListEqual([fr],
                             fc.get_neighbors(directions=[N, E]))
        self.assertListEqual([None, fr],
                             fc.get_neighbors(allow_none=True,
                                              directions=[N, E]))
        fc.update_neighbor(N, fa)

        # Empty cells.
        fe = EmptyCell()
        fc.set_neighbor(E, fe)
        self.assertListEqual([fa, fl, fb, fe], fc.get_neighbors())
        self.assertListEqual([fa, fl, fb, fr],
                             fc.get_neighbors(allow_empty=False))

    def test_is_overlap(self) -> None:
        bbox1 = BBox(3, 10, 6, 11)
        bbox2 = BBox(6, 11, 7, 12)
        bbox3 = BBox(1, 11, 4, 12)
        f1 = Cell("f1", bbox1)
        f2 = Cell("f2", bbox2)
        f3 = Cell("f3", bbox3)
        # Each cell overlaps with itself.
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
        f1 = Cell("f1", bbox1)
        f2 = Cell("f2", bbox2)
        f3 = Cell("f3", bbox3)
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
        f1 = Cell("f1", bbox1.copy())
        f2 = Cell("f2", bbox2.copy())
        f3 = Cell("f3", bbox3.copy())
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

    def test_prev_next(self) -> None:
        a, b, c = create_cells(3)
        self.assertIsNone(b.prev)
        b.prev = a
        self.assertEqual(a, b.prev)
        self.assertEqual(b, a.next)
        self.assertEqual(a, a.next.prev)
        self.assertEqual(b, b.prev.next)

        # Insert a node (c) between two other nodes (a, b).
        self.assertIsNone(c.prev)
        self.assertIsNone(c.next)
        a.next = c
        self.assertEqual(a, c.prev)
        self.assertEqual(b, c.next)

    def test_above_below(self) -> None:
        a, b, c = create_cells(3)
        self.assertIsNone(b.above)
        b.above = a
        self.assertEqual(a, b.above)
        self.assertEqual(b, a.below)
        self.assertEqual(a, a.below.above)
        self.assertEqual(b, b.above.below)

        # Insert a node (c) between two other nodes (a, b).
        self.assertIsNone(c.above)
        self.assertIsNone(c.below)
        a.below = c
        self.assertEqual(a, c.above)
        self.assertEqual(b, c.below)

    def test_update_neighbor(self) -> None:
        a, b, c, d = create_cells(4)

        a.update_neighbor(E, b)
        self.assertEqual(a.get_neighbor(E), b)
        self.assertEqual(b.get_neighbor(W), a)
        self.assertIsNone(a.get_neighbor(S))
        self.assertIsNone(a.get_neighbor(N))
        self.assertIsNone(b.get_neighbor(S))
        self.assertIsNone(b.get_neighbor(N))
        c.update_neighbor(E, d)
        c.update_neighbor(W, b)
        self.assertListEqual([a, b, c, d], list(a.iter(E)))
        self.assertListEqual([d, c, b, a], list(d.iter(W)))

        e = Cell("e")
        b.update_neighbor(E, e)
        lst = [a, b, e, c, d]
        self.assertListEqual(lst, list(a.iter(E)))
        self.assertListEqual(list(reversed(lst)), list(d.iter(W)))

        f = Cell("f")
        g = Cell("g")
        f.update_neighbor(E, g)
        # Removing the neighbor on one node, removes it from the other as well.
        f.update_neighbor(E, None)
        self.assertIsNone(f.get_neighbor(E))
        self.assertIsNone(g.get_neighbor(W))
        # However, this works, because the order is clear.
        e.update_neighbor(E, f)
        f.update_neighbor(E, g)
        lst = [a, b, e, f, g, c, d]
        self.assertListEqual(lst, list(a.iter(E)))
        self.assertListEqual(list(reversed(lst)), list(d.iter(W)))

    def test_iter(self) -> None:
        d = E
        # TODO: Test with complete=True
        cells = create_cells(5, link_d=d)
        for i in range(1, len(cells)):
            start: Cell = cells[i]
            with self.subTest(start=start):
                self.assertListEqual([start.prev] + list(start.iter(d, False)),
                                     list(start.prev.iter(d, False)))
                self.assertTrue(all(n in cells for n in start.iter(d, False)))
        a = Cell("a")
        start = cells[0]
        self.assertNotIn(a, start.iter(d))
        a.set_neighbor(d, start)
        self.assertListEqual([a] + list(cells), list(a.iter(d)))


def create_cells(num: int, *, link_d: Direction | None = None
                 ) -> tuple[Cell, ...]:
    nodes = tuple(Cell(text=chr(97 + i)) for i in range(num))
    if link_d:
        p = peekable(nodes)
        for node in p:
            node.next = p.peek(None)

    return nodes
