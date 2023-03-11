from math import inf

from pdf2gtfs.locate.finder.cost import Cost, StartCost
from test import P2GTestCase


class TestCost(P2GTestCase):
    def setUp(self) -> None:
        self.cost_1 = Cost(1, 2, 3, 4)
        self.cost_2 = Cost(5, 4, 3, 2)
        self.cost_3 = Cost(1, 2, 3, 4)
        self.cost_4 = Cost(4, 4, 4, 4)
        self.cost_5 = Cost(4, 4, 3, 5)
        self.cost_inf = Cost(1, inf, 1, 1)

    def test__get_cost(self) -> None:
        self.assertEqual(inf, Cost._get_cost(None))
        self.assertEqual(inf, Cost._get_cost(-1))
        self.assertEqual(inf, Cost._get_cost(inf))
        self.assertEqual(3.3, Cost._get_cost(3.3))

    def test_as_float(self) -> None:
        self.assertEqual(10, self.cost_1.as_float)
        self.assertEqual(14, self.cost_2.as_float)
        self.assertEqual(10, self.cost_3.as_float)
        self.assertEqual(16, self.cost_4.as_float)
        self.assertEqual(16, self.cost_5.as_float)
        self.assertEqual(inf, self.cost_inf.as_float)

    def test_travel_cost(self) -> None:
        cost = Cost()
        self.assertEqual(inf, cost.travel_cost)
        cost.travel_cost = 10
        self.assertEqual(10, cost.travel_cost)
        cost.travel_cost = 300
        self.assertEqual(100, cost.travel_cost)

    def test_costs(self) -> None:
        self.assertEqual((1, 2, 3, 4), self.cost_1.costs)
        self.assertEqual((5, 4, 3, 2), self.cost_2.costs)
        self.assertEqual((1, 2, 3, 4), self.cost_3.costs)
        self.assertEqual((4, 4, 4, 4), self.cost_4.costs)
        self.assertEqual((4, 4, 3, 5), self.cost_5.costs)
        self.assertEqual((1, inf, 1, 1), self.cost_inf.costs)

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

    def test_ge(self) -> None:
        self.assertGreaterEqual(self.cost_1, self.cost_3)
        self.assertGreaterEqual(self.cost_5, self.cost_4)
        self.assertGreaterEqual(self.cost_5, self.cost_3)
        self.assertGreaterEqual(self.cost_5, self.cost_2)
        self.assertGreaterEqual(self.cost_5, self.cost_1)
        self.assertGreaterEqual(self.cost_2, self.cost_1)
        self.assertGreaterEqual(self.cost_2, self.cost_3)


class TestStartCost(P2GTestCase):
    def test_from_cost(self) -> None:
        start_cost = StartCost()
        self.assertEqual(Cost().costs, start_cost.costs)
        cost = Cost(1, 2, 3, 4)
        start_cost = StartCost.from_cost(cost)
        self.assertEqual((0, 2, 3, 0), start_cost.costs)
