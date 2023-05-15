import pdf2gtfs.locate.finder.osm_values as osmv
from pdf2gtfs.config import Config
from pdf2gtfs.datastructures.gtfs_output.routes import RouteType
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

    def test_new_osm_values(self) -> None:
        for rt in ["Tram", "StreetCar", "LightRail", "Subway", "Metro", "Rail",
                   "Bus", "Ferry", "CableTram", "AerialLift",
                   "SuspendedCableCar", "Funicular", "Monorail"]:
            Config.gtfs_routtype = rt
            i1, e1 = osmv.get_all_cat_scores()
            i2, e2 = osmv.get_all_cat_scores_old()
            self.assertDictEqual(i1, i2)
            self.assertDictEqual(e1, e2)
