import locate.finder.location as loc
from test import P2GTestCase


class TestLocation(P2GTestCase):
    def setUp(self) -> None:
        self.loc1 = loc.Location(47.5, 7.8)
        self.loc2 = loc.Location(48.5, 7.9)

    def test__clean_value(self) -> None:
        self.assertEqual(0, loc.Location._clean_value(91))
        self.assertEqual(0, loc.Location._clean_value(-91))
        self.assertEqual(8.12346, loc.Location._clean_value(8.12345678))
        self.assertEqual(48.0, loc.Location._clean_value(48))

    def test_is_valid(self) -> None:
        self.assertTrue(self.loc1.is_valid)
        self.assertTrue(self.loc2.is_valid)
        self.assertFalse(loc.Location(0, 7.8).is_valid)
        self.assertFalse(loc.Location(48, 0).is_valid)
        self.assertFalse(loc.Location(-100, 100).is_valid)
        self.assertFalse(loc.Location(100, 4).is_valid)

    def test_add(self) -> None:
        self.assertEqual(self.loc2, self.loc1 + loc.Location(1, 0.1))
        self.assertEqual(self.loc1, self.loc2 + loc.Location(-1, -0.1))

    def test_sub(self) -> None:
        self.assertEqual(loc.Location(1, 0.1), self.loc2 - self.loc1)
        self.assertEqual(loc.Location(-1, -0.1), self.loc1 - self.loc2)
        self.assertEqual(loc.Location(0, 0), self.loc1 - self.loc1)

    def test_distances(self) -> None:
        dists = self.loc1.distances(self.loc2)
        self.assertEqual(loc.DISTANCE_IN_M_PER_LAT_DEG, next(dists))
        self.assertAlmostEqual(loc.get_distance_per_lon_deg(48) * 0.1,
                               next(dists))
        dists = self.loc1.distances(self.loc1)
        self.assertEqual(0, next(dists))
        self.assertEqual(0, next(dists))

    def test_get_distance_per_lon_deg(self) -> None:
        self.assertEqual(loc.DISTANCE_IN_M_PER_LAT_DEG,
                         loc.get_distance_per_lon_deg(0))
        self.assertAlmostEqual(0.0, loc.get_distance_per_lon_deg(90))
        self.assertEqual(loc.get_distance_per_lon_deg(45),
                         loc.get_distance_per_lon_deg(-45))
        self.assertAlmostEqual(74487.6191, loc.get_distance_per_lon_deg(48), 4)
