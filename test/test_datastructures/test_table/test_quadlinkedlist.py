from unittest import TestCase

from pdf2gtfs.datastructures.table.nodes import QuadNode
from pdf2gtfs.datastructures.table.direction import E, N, S, W


class TestQuadNode(TestCase):
    def test_set_neighbor(self) -> None:
        a = QuadNode()
        b = QuadNode()
        c = QuadNode()
        d = QuadNode()

        a.set_neighbor(E, b)
        self.assertEqual(a.get_neighbor(E), b)
        self.assertEqual(b.get_neighbor(W), a)
        self.assertIsNone(a.get_neighbor(S))
        self.assertIsNone(a.get_neighbor(N))
        self.assertIsNone(b.get_neighbor(S))
        self.assertIsNone(b.get_neighbor(N))
        c.set_neighbor(E, d)
        c.set_neighbor(W, b)
        self.assertListEqual([a, b, c, d], list(a.iter(E)))
        self.assertListEqual([d, c, b, a], list(d.iter(W)))

        e = QuadNode()
        b.set_neighbor(E, e)
        lst = [a, b, e, c, d]
        self.assertListEqual(lst, list(a.iter(E)))
        self.assertListEqual(list(reversed(lst)), list(d.iter(W)))

        f = QuadNode()
        g = QuadNode()
        f.set_neighbor(E, g)
        with self.assertRaises(AssertionError):
            b.set_neighbor(E, f)
        # Removing the neighbor on one node, removes it from the other as well.
        f.set_neighbor(E, None)
        self.assertIsNone(f.get_neighbor(E))
        self.assertIsNone(g.get_neighbor(W))
        # However, this works, because the order is clear.
        e.set_neighbor(E, f)
        f.set_neighbor(E, g)
        lst = [a, b, e, f, g, c, d]
        self.assertListEqual(lst, list(a.iter(E)))
        self.assertListEqual(list(reversed(lst)), list(d.iter(W)))
