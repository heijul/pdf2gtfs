from unittest import TestCase

from more_itertools import peekable

from pdf2gtfs.datastructures.table.nodes import QuadNode
from pdf2gtfs.datastructures.table.direction import Direction, E, N, S, W


# TODO NOW: Set neighbors to None; Reverse neighbor setting.


class TestQuadNode(TestCase):
    def test_prev_next(self) -> None:
        a, b, c = create_quad_nodes(3)
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
        a, b, c = create_quad_nodes(3)
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

    def test_set_neighbor(self) -> None:
        a, b, c, d = create_quad_nodes(4)

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

    def test_iter(self) -> None:
        d = E
        nodes = create_quad_nodes(5, link_d=d)
        for i in range(1, len(nodes)):
            start = nodes[i]
            with self.subTest(start=start):
                self.assertListEqual([start.prev] + list(start.iter(d)),
                                     list(start.prev.iter(d)))
                self.assertTrue(all(n in nodes for n in start.iter(d)))
        a = QuadNode()
        start = nodes[0]
        self.assertNotIn(a, start.iter(d))
        a.set_neighbor(d, start)
        self.assertListEqual([a] + list(nodes), list(a.iter(d)))


def create_quad_nodes(num: int, *, link_d: Direction | None = None
                      ) -> tuple[QuadNode, ...]:
    nodes = tuple(QuadNode() for _ in range(num))
    if link_d:
        p = peekable(nodes)
        for node in p:
            node.next = p.peek(None)

    return nodes
