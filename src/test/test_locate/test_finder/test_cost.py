from math import inf

from locate.finder.cost import Cost
from test import P2GTestCase


class TestCost(P2GTestCase):
    def setUp(self) -> None:
        self.cost_1 = Cost(1, 2, 3, 4)
        self.cost_2 = Cost(5, 4, 3, 2)
        self.cost_3 = Cost(1, 2, 3, 4)
        self.cost_4 = Cost(4, 4, 4, 4)
        self.cost_5 = Cost(4, 4, 3, 5)
        self.cost_inf = Cost(1, inf, 1, 1)

    def test_from_cost(self) -> None:
        self.assertNotEqual(id(self.cost_1), id(Cost.from_cost(self.cost_1)))
        self.assertEqual(self.cost_1, Cost.from_cost(self.cost_1))
        self.assertEqual(self.cost_2, Cost.from_cost(self.cost_2))
        self.assertEqual(self.cost_3, Cost.from_cost(self.cost_3))

        self.assertEqual(self.cost_3, Cost.from_cost(self.cost_1))

    def test_eq(self) -> None:
        self.assertEqual(self.cost_1, self.cost_1)
        self.assertEqual(self.cost_1, self.cost_3)
        self.assertEqual(self.cost_4, self.cost_5)
        self.assertEqual(self.cost_3, self.cost_1)

        self.assertNotEqual(self.cost_1, self.cost_4)

        self.assertEqual(self.cost_inf, self.cost_inf)
        self.assertNotEqual(self.cost_1, self.cost_inf)
        # Stop ordering matters.
        self.assertNotEqual(self.cost_3, self.cost_2)
        self.assertNotEqual(self.cost_3.costs, self.cost_2.costs)

    def test_lt(self) -> None:
        self.assertLess(self.cost_1, self.cost_4)
        self.assertLess(self.cost_2, self.cost_4)

    def test_le(self) -> None:
        self.assertLessEqual(self.cost_1, self.cost_2)
        self.assertGreater(self.cost_2, self.cost_1)
        self.assertGreater(self.cost_2, self.cost_3)
        self.assertLessEqual(self.cost_3, self.cost_1)

    def test_gt(self) -> None:
        for i in range(1, 4):
            self.assertGreater(self.cost_4, getattr(self, f"cost_{i}"))