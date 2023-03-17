from __future__ import annotations

from pathlib import Path

from custom_conf.config import BaseConfig
from custom_conf.properties.property import Property

import pdf2gtfs.config.errors as err
from pdf2gtfs.config import (
    AbbrevProperty, AverageSpeedProperty, DateBoundsProperty,
    FilenameProperty, HeaderValuesProperty, HolidayCodeProperty,
    InputProperty, OutputPathProperty, PagesProperty,
    RepeatIdentifierProperty, RouteTypeProperty)
from pdf2gtfs.config.properties import Pages

from test import P2GTestCase, TEST_DIR


class P2GQuietTestCase(P2GTestCase):
    @classmethod
    def setUpClass(cls: P2GTestCase, create_temp_dir: bool = False,
                   disable_logging: bool = True) -> None:
        super().setUpClass(create_temp_dir, disable_logging)


class DummyConfig(BaseConfig):
    def _initialize_config_properties(self) -> None:
        self.repeat_ident = RepeatIdentifierProperty("repeat_ident")
        self.header_values = HeaderValuesProperty("header_values")
        self.holiday_code = HolidayCodeProperty("holiday_code")
        self.pages = PagesProperty("pages")
        self.filename = FilenameProperty("filename", str)
        self.gtfs_routetype = RouteTypeProperty("gtfs_routetype")
        self.output_path = OutputPathProperty("output_path")
        self.datebounds = DateBoundsProperty("datebounds")
        self.abbreviations = AbbrevProperty("abbreviations")
        self.average_speed = AverageSpeedProperty("average_speed")
        self.input = InputProperty("input")
        super()._initialize_config_properties()

    @property
    def config_dir(self) -> Path:
        return TEST_DIR

    @property
    def default_config_path(self) -> Path:
        return self.config_dir

    def get_property(self, name: str) -> Property | None:
        """ Return the property object with the given name or None. """
        try:
            return object.__getattribute__(self, name)
        except AttributeError:
            return None


class TestRepeatIdentifierProperty(P2GQuietTestCase):
    def test__validate_length(self) -> None:
        repeat_ident = RepeatIdentifierProperty("repeat_ident")
        valids = [["Alle", "Minuten"], ["Repeats every", "minutes"]]
        invalids = [["Alle", "X", "Minutes"], ["Repeats every minutes"], []]
        repeat_ident._validate_length(valids)
        for i, invalid_value in enumerate(invalids):
            with (self.subTest(i=i),
                  self.assertRaises(err.InvalidRepeatIdentifierError)):
                repeat_ident._validate_length([invalid_value])


class TestHeaderValuesProperty(P2GQuietTestCase):
    def test__validate_header_values(self) -> None:
        header_values = HeaderValuesProperty("header_values")
        valid_values = [{"weekdays": "1,2,3,4,5"},
                        {"weekdays": "0, 1, 2,3,4"},
                        {"weekdays": "1, 2, 3, 4, 5"},
                        {"weekends": ["5", "6"]},
                        {"holidays": "h"},
                        {}]
        invalid_values = [{"weekends": "sunday,saturday"},
                          {"holidays": "3112"},
                          {"weekends": ["5", "6h"]},
                          {"weekends": ["6", "7"]},
                          {"other days": "-1"}]
        for i, value in enumerate(valid_values):
            with self.subTest(i=i):
                try:
                    header_values._validate_header_values(value)
                except err.InvalidHeaderDaysError:
                    self.fail("InvalidHeaderDaysError raised")
        for j, value in enumerate(invalid_values):
            with (self.subTest(j=j),
                  self.assertRaises(err.InvalidHeaderDaysError)):
                header_values._validate_header_values(value)

    def test_set(self) -> None:
        c = DummyConfig()
        values = [{"weekdays": "1, 2,3 , 5, 4"},
                  {"weekends": ["h", "5", "6"]}]
        results = [{"weekdays": ["1", "2", "3", "4", "5"]},
                   {"weekends": ["5", "6", "h"]}]
        for i, (value, result) in enumerate(zip(values, results, strict=True)):
            with self.subTest(i=i):
                c.header_values = value
                self.assertEqual(result, c.header_values)


class TestHolidayCodeProperty(P2GQuietTestCase):
    def test__validate_holiday_code(self) -> None:
        holiday_code = HolidayCodeProperty("holiday_code")
        valid_codes = [{"country": "DE", "subdivision": "BW"},
                       {"country": "de", "subdivision": "BW"},
                       {"country": "", "subdivision": "BW"},
                       {"country": "de", "subdivision": ""}]
        invalid_codes = [{"country": "test"},
                         {"country": "DE", "subdivision": "AZ"}]
        for i, valid_code in enumerate(valid_codes):
            with self.subTest(i=i):
                try:
                    holiday_code._validate_holiday_code(valid_code)
                except err.InvalidHolidayCodeError:
                    self.fail("InvalidHolidayCodeError raised")
        for j, invalid_code in enumerate(invalid_codes):
            with (self.subTest(j=j),
                  self.assertRaises(err.InvalidHolidayCodeError)):
                holiday_code._validate_holiday_code(invalid_code)

    def test_set(self) -> None:
        c = DummyConfig()
        values = [["", "BW"], ["DE", "BW"], ["de", "bw"],
                  ["DE", ""]]
        results = [(None, None), ("DE", "BW"), ("DE", "BW"),
                   ("DE", "")]
        for i, (value, result) in enumerate(zip(values, results, strict=True)):
            with self.subTest(i=i):
                c.holiday_code = {"country": value[0], "subdivision": value[1]}
                self.assertEqual(result, c.holiday_code)


class TestPages(P2GQuietTestCase):
    def test_set_value(self) -> None:
        pages = Pages()
        pages.set_value("all")
        self.assertTrue(pages.all)
        self.assertEqual([], pages.pages)
        pages.set_value("1      3, 2 -  4")
        self.assertFalse(pages.all)
        self.assertEqual([2, 3, 4, 13], pages.pages)

    def test_page_ids(self) -> None:
        pages = Pages()
        self.assertIsNone(pages.page_ids)
        self.assertEqual([], pages.pages)
        pages.set_value("1, 2, 3, 4, 5")
        self.assertEqual([0, 1, 2, 3, 4], pages.page_ids)
        pages.set_value("1-5")
        self.assertEqual([0, 1, 2, 3, 4], pages.page_ids)

    def test__page_string_to_pages(self) -> None:
        self.assertEqual((True, []), Pages._page_string_to_pages(" a l l "))
        self.assertEqual((False, [13, 23, 33]),
                         Pages._page_string_to_pages("1  3, 33, 23"))
        self.assertEqual((False, list(range(1, 100))),
                         Pages._page_string_to_pages("1-99"))

    def test_page_num(self) -> None:
        pages = Pages()
        pages.set_value("3-8")
        results = range(3, 9)
        # pdfminer's page ids are 1-indexed.
        for i in range(1, 6):
            with self.subTest(i=i):
                self.assertEqual(results[i - 1], pages.page_num(i))

    def test_remove_invalid_pages(self) -> None:
        pages = Pages()
        self.assertEqual([], pages.pages)
        pages.all, pages.pages = pages._page_string_to_pages("0,1,3-6")
        self.assertEqual([0, 1, 3, 4, 5, 6], pages.pages)
        pages.remove_invalid_pages()
        self.assertEqual([1, 3, 4, 5, 6], pages.pages)
        pages.all, pages.pages = pages._page_string_to_pages("0")
        self.assertEqual([0], pages.pages)
        with self.assertRaises(SystemExit):
            pages.remove_invalid_pages()


class TestPage(P2GTestCase):
    def test_set(self) -> None:
        c = DummyConfig()
        pages = Pages()
        pages.set_value("1,2,4-6")
        c.pages = pages
        self.assertEqual(pages, c.pages)
        c.pages = "all"
        self.assertEqual(True, c.pages.all)
        self.assertEqual([], c.pages.pages)


class TestRouteTypeProperty(P2GTestCase):
    def test__validate_route_type(self) -> None:
        valid_values = ["Tram", "tram", "TRAM", "1", "2", "3", "11", "12"]
        invalid_values = ["tr a m", "test", "22"]
        for i, valid_value in enumerate(valid_values):
            with self.subTest(i=i):
                try:
                    RouteTypeProperty._validate_route_type(valid_value)
                except err.InvalidRouteTypeValueError:
                    self.fail("InvalidRouteTypeValueError raised")
        for j, invalid_value in enumerate(invalid_values):
            with (self.subTest(j=j),
                  self.assertRaises(err.InvalidRouteTypeValueError)):
                RouteTypeProperty._validate_route_type(invalid_value)

    def test_set(self) -> None:
        c = DummyConfig()
        values = ["Tram", "tram", "bus", "Bus", "0", "2", "3", "5", "11", "12"]
        results = ["Tram", "Tram", "Bus", "Bus", "Tram", "Rail", "Bus",
                   "CableTram", "Trolleybus", "Monorail"]
        for i, (value, result) in enumerate(zip(values, results, strict=True)):
            with self.subTest(i=i):
                c.gtfs_routetype = value
                self.assertEqual(result, c.gtfs_routetype)


class TestOutputPathProperty(P2GQuietTestCase):
    @classmethod
    def setUpClass(cls: P2GTestCase, create_temp_dir: bool = True,
                   disable_logging: bool = True) -> None:
        super().setUpClass(create_temp_dir, disable_logging)

    def test__validate_path(self) -> None:
        path = Path(self.temp_dir.name)
        existing_zip_path = path.joinpath("test_exists.zip")
        invalid_file_ending = path.joinpath("test.txt")
        # Create empty zip.
        for file_name in existing_zip_path, invalid_file_ending:
            with open(file_name, "w", encoding="utf-8") as file:
                file.write("")
        non_existing_zip_path = path.joinpath("tests_new.zip")
        invalid_file_ending = path.joinpath("test.txt")

        valid_values = [path, non_existing_zip_path, existing_zip_path]
        invalid_values = [invalid_file_ending]
        for i, valid_value in enumerate(valid_values):
            with self.subTest(i=i):
                try:
                    OutputPathProperty._validate_path(valid_value)
                except err.InvalidOutputPathError:
                    self.fail("InvalidOutputPathError raised")
        for j, invalid_value in enumerate(invalid_values):
            with (self.subTest(j=j),
                  self.assertRaises(err.InvalidOutputPathError)):
                OutputPathProperty._validate_path(invalid_value)

    def test_set(self) -> None:
        c = DummyConfig()
        path = Path(self.temp_dir.name)
        zip_path = path.joinpath("test.zip")
        values = [str(path), zip_path, str(zip_path)]
        results = [path, zip_path, zip_path]
        for i, (value, result) in enumerate(zip(values, results, strict=True)):
            c.output_path = value
            self.assertEqual(result, c.output_path)


class TestDateBoundsProperty(P2GTestCase):
    def test_clean_value(self) -> None:
        valid_values = ["", ["", ""], ["20221004", ""], ["", "20221004"]]
        invalid_values = [[""], ["20220229", ""], ["202202", ""]]
        for i, valid_value in enumerate(valid_values):
            with self.subTest(i=i):
                try:
                    DateBoundsProperty.clean_value(valid_value)
                except err.InvalidDateBoundsError:
                    self.fail("InvalidDateBoundsError raised")
        for j, invalid_value in enumerate(invalid_values):
            with (self.subTest(j=j),
                  self.assertRaises(err.InvalidDateBoundsError)):
                DateBoundsProperty.clean_value(invalid_value)

    def test_set(self) -> None:
        c = DummyConfig()
        values = ["", ["20220202", "20221010"]]
        for i, value in enumerate(values):
            with self.subTest(i=i):
                c.datebounds = value
                result = DateBoundsProperty.clean_value(value)
                self.assertEqual(result, c.datebounds)


class TestAbbrevProperty(P2GTestCase):
    def test_clean_value(self) -> None:
        values = {"hbf.": "hauptbahnhof", "bf.    ": "bahnhof",
                  "bf": "Bahnhof",
                  "longtest": "shorter", "ßhorttest": "longer  "}
        clean_values = {"sshorttest": "longer", "longtest": "shorter",
                        "hbf.": "hauptbahnhof", "bf.": "bahnhof",
                        "bf": "bahnhof"}
        self.assertEqual(clean_values, AbbrevProperty.clean_value(values))

    def test_set(self) -> None:
        c = DummyConfig()
        values = [{"a": "am", "aa": "aam"}, {},
                  {"hbf.": "hauptbahnhof", "bf.    ": "bahnhof",
                   "bf": "Bahnhof", "longtest": "shorter",
                   "ßhorttest": "longer  "}]
        for i, value in enumerate(values):
            with self.subTest(i=i):
                clean_value = AbbrevProperty.clean_value(value)
                c.abbreviations = value
                self.assertEqual(clean_value, c.abbreviations)


class TestAverageSpeedProperty(P2GTestCase):
    def test___get__(self) -> None:
        c = DummyConfig()
        # Default average speed depends on the route type,
        # but only if it is set to 0.
        c.average_speed = 0
        c.gtfs_routetype = "tram"
        self.assertEqual(25, c.average_speed)
        c.gtfs_routetype = "monorail"
        self.assertEqual(35, c.average_speed)
        for value in range(1, 201):
            c.average_speed = value
            self.assertEqual(value, c.average_speed)
