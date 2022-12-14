import locate.finder.osm_values as osmv
from config import Config
from datastructures.gtfs_output.routes import RouteType
from test import P2GTestCase


class TestOSMValues(P2GTestCase):
    def test_get_all_cat_scores(self) -> None:
        Config.gtfs_routetype = "Tram"
        cat_scores1 = osmv.get_all_cat_scores()
        Config.gtfs_routetype = "Bus"
        cat_scores2 = osmv.get_all_cat_scores()
        self.assertNotEqual(cat_scores1, cat_scores2)
        self.assertEqual(cat_scores1[0], osmv.Tram().good_values)
        self.assertEqual(cat_scores1[1], osmv.Tram().bad_values)
        self.assertEqual(cat_scores2[0], osmv.Bus().good_values)
        self.assertEqual(cat_scores2[1], osmv.Bus().bad_values)

    def test_get_osm_values(self) -> None:
        values = osmv.get_osm_values()
        for i, name in enumerate(values):
            with self.subTest(i=i):
                try:
                    RouteType[name]
                except KeyError:
                    self.fail(f"KeyError raised for {name}")
