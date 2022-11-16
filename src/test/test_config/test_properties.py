from pathlib import Path

import config.errors as err
import config.properties as p
from config import InstanceDescriptorMixin
from test import P2GTestCase


class DummyConfig(InstanceDescriptorMixin):
    def __init__(self) -> None:
        self.properties = []


class PropertyTestCase(P2GTestCase):
    @classmethod
    def setUpClass(cls: P2GTestCase, **kwargs) -> None:
        kwargs["disable_logging"] = True
        super().setUpClass(**kwargs)

    def setUp(self) -> None:
        self.dummy = DummyConfig()

    def get_property(self, name: str) -> p.Property | None:
        """ Return the property object with the given name or None. """
        try:
            return object.__getattribute__(self.dummy, name)
        except AttributeError:
            return None


class TestProperty(PropertyTestCase):
    def test__register(self) -> None:
        self.assertFalse(hasattr(self.dummy, "__test_property"))
        self.dummy.properties = []
        self.dummy.test_property = p.Property(self.dummy, "test_property", int)
        self.dummy.test_property = 200

        prop = self.get_property("test_property")
        self.assertTrue(hasattr(self.dummy, "__test_property"))
        self.assertEqual(self.dummy, prop.cls)
        self.assertEqual(200, prop.__get__(self.dummy))

    def test___get__(self) -> None:
        self.dummy.prop = p.Property(self.dummy, "prop", int)
        with self.assertRaises(err.MissingRequiredPropertyError):
            _ = self.dummy.prop
        self.dummy.prop = 200
        self.assertEqual(200, self.dummy.prop)

    def test_validate(self) -> None:
        types = [int, float, str, list]
        props = ["prop_int", "prop_float", "prop_str", "prop_list"]
        values = [float("inf"), "test", [], "test"]
        self.dummy.prop = p.Property(self.dummy, "prop", int)
        for i in range(4):
            prop = props[i]
            setattr(self.dummy, prop, p.Property(self.dummy, prop, types[i]))
            with self.subTest(i=i):
                with self.assertRaises(err.InvalidPropertyTypeError):
                    setattr(self.dummy, prop, values[i])

    def test__raise_type_error(self) -> None:
        self.dummy.prop = p.Property(self.dummy, "prop", int)
        with self.assertRaises(err.InvalidPropertyTypeError):
            self.get_property("prop")._raise_type_error(str)

    def test__validate_type(self) -> None:
        self.dummy.prop = p.Property(self.dummy, "prop", int)
        values = ["test", [1], {1: 1}, {1, 2}]
        for i in range(len(values)):
            with (self.subTest(i=i),
                  self.assertRaises(err.InvalidPropertyTypeError)):
                self.get_property("prop")._validate_type(values[i])

    def test___set__(self) -> None:
        self.dummy.prop = p.Property(self.dummy, "prop", int)
        prop = self.get_property("prop")
        with self.assertRaises(err.InvalidPropertyTypeError):
            prop.__set__(self.dummy, "22")
        with self.assertRaises(err.MissingRequiredPropertyError):
            _ = self.dummy.prop
        self.dummy.prop = 22
        self.assertEqual(22, self.dummy.prop)


class TestBoundsProperty(PropertyTestCase):
    def get_property(self, name: str) -> p.BoundsProperty | None:
        return super().get_property(name)

    def test___init__(self) -> None:
        self.dummy.prop = p.BoundsProperty(self.dummy, "prop", int, 1, 2)
        bounds = [[1.0, 2], [1, "2"], [[2], 1]]
        for i in range(len(bounds)):
            with (self.subTest(i=i),
                  self.assertRaises(err.InvalidPropertyTypeError)):
                self.dummy.prop = p.BoundsProperty(
                    self.dummy, "prop", int, bounds[i][0], bounds[i][1])

    def test_validate(self) -> None:
        self.dummy.prop = p.BoundsProperty(self.dummy, "prop", int, -1, 5)
        prop = self.get_property("prop")
        # Ensure normal type checking still works.
        with self.assertRaises(err.InvalidPropertyTypeError):
            prop.validate("2")
        oor_values = [22, -4, -2, 100, 6]
        for i in range(len(oor_values)):
            with (self.subTest(i=i),
                  self.assertRaises(err.OutOfBoundsPropertyError)):
                prop.validate(oor_values[i])
        # No errors raised
        for i, value in enumerate(range(-1, 6)):
            with self.subTest(i=i):
                try:
                    prop.validate(value)
                except (err.OutOfBoundsPropertyError,
                        err.InvalidPropertyTypeError):
                    self.fail("OutOfBoundsPropertyError raised")

    def test__validate_within_bounds(self) -> None:
        self.dummy.prop = p.BoundsProperty(self.dummy, "prop", int, -1, 5)
        prop = self.get_property("prop")
        # Ensure normal type checking fails for different reasons.
        with self.assertRaises(TypeError):
            prop._validate_within_bounds("22")
        oor_values = [22, -4, -2, 100, 6]
        for i in range(len(oor_values)):
            with (self.subTest(i=i),
                  self.assertRaises(err.OutOfBoundsPropertyError)):
                prop.validate(oor_values[i])
        # No errors raised
        for i, value in enumerate(range(-1, 6)):
            with self.subTest(i=i):
                try:
                    prop.validate(value)
                except err.OutOfBoundsPropertyError:
                    self.fail("OutOfBoundsPropertyError raised")
                except err.InvalidPropertyTypeError:
                    self.fail("InvalidPropertyTypeError raised")


class TestNestedTypeProperty(PropertyTestCase):
    # TODO: Probably need to test the other validate_x methods as well...
    def get_property(self, name: str) -> p.BoundsProperty | None:
        return super().get_property(name)

    def test__validate_type(self) -> None:
        # TODO: More types.
        types = [dict[str: tuple[int, float]]]
        valids = [
            {}, {"test": tuple()}, {"test": (1, 3.3)}, {"test": (1.1, 3)}]
        invalids = [[], "test", {"test", (1, 23.3)}, {"test": [1, 3.2]}]
        self._test_prop_type_value(types, valids, invalids, "_validate_type")

    def _test_prop_type_value(self, types, valids, invalids,
                              func_name) -> None:
        """ Create a property for each type checking the values. """
        for i, typ in enumerate(types):
            prop = p.NestedTypeProperty(self.dummy, f"prop_{typ}", typ)
            func = getattr(prop, func_name)
            with self.subTest(i=i):
                for j, invalid_value in enumerate(invalids):
                    with (self.subTest(j=j),
                          self.assertRaises(err.InvalidPropertyTypeError)):
                        func(invalid_value)
                for k, valid_value in enumerate(valids):
                    with self.subTest(k=k):
                        try:
                            func(valid_value)
                        except err.InvalidPropertyTypeError:
                            self.fail("OutOfBoundsPropertyError raised")

    def test__validate_generic_type(self) -> None:
        # Skipping this test, because it is tested in _test__validate_type.
        pass

    def test_validate_generic_dict(self) -> None:
        # Skipping this test, because it is tested in _test__validate_type.
        pass

    def test_validate_generic_iterable(self) -> None:
        # Skipping this test, because it is tested in _test__validate_type.
        pass

    def test__validate_generic_type_args(self) -> None:
        # Skipping this test, because it is tested in _test__validate_type.
        pass


class TestRepeatIdentifierProperty(PropertyTestCase):
    def get_property(self, name: str) -> p.RepeatIdentifierProperty | None:
        return super().get_property(name)

    def test__validate_length(self) -> None:
        prop = p.RepeatIdentifierProperty(self.dummy, "prop")
        valids = [["Alle", "Minuten"], ["Repeats with period:", ""]]
        invalids = [["Alle", "X", "Minutes"], ["Repeats with period:"],
                    []]
        try:
            prop._validate_length(valids)
        except err.InvalidRepeatIdentifierError:
            self.fail("InvalidRepeatIdentifierError raised")
        for i, invalid_value in enumerate(invalids):
            with (self.subTest(i=i),
                  self.assertRaises(err.InvalidRepeatIdentifierError)):
                prop._validate_length([invalid_value])


class TestHeaderValuesProperty(PropertyTestCase):
    def get_property(self, name: str) -> p.HeaderValuesProperty | None:
        return super().get_property(name)

    def test__validate_header_values(self) -> None:
        prop = p.HeaderValuesProperty(self.dummy, "prop")
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
                    prop._validate_header_values(value)
                except err.InvalidHeaderDaysError:
                    self.fail("InvalidHeaderDaysError raised")
        for j, value in enumerate(invalid_values):
            with (self.subTest(j=j),
                  self.assertRaises(err.InvalidHeaderDaysError)):
                prop._validate_header_values(value)

    def test___set__(self) -> None:
        prop = p.HeaderValuesProperty(self.dummy, "prop")
        values = [{"weekdays": "1, 2,3 , 5, 4"},
                  {"weekends": ["h", "5", "6"]}]
        results = [{"weekdays": ["1", "2", "3", "4", "5"]},
                   {"weekends": ["5", "6", "h"]}]
        for i, (value, result) in enumerate(zip(values, results, strict=True)):
            with self.subTest(i=i):
                prop.__set__(self.dummy, value)
                self.assertEqual(result, prop.__get__(self.dummy))


class TestHolidayCodeProperty(PropertyTestCase):
    def get_property(self, name: str) -> p.HolidayCodeProperty | None:
        return super().get_property(name)

    def test__validate_holiday_code(self) -> None:
        prop = p.HolidayCodeProperty(self.dummy, "prop")
        valid_codes = [{"country": "DE", "subdivision": "BW"},
                       {"country": "de", "subdivision": "BW"},
                       {"country": "", "subdivision": "BW"},
                       {"country": "de", "subdivision": ""}]
        invalid_codes = [{"country": "test"},
                         {"country": "DE", "subdivision": "AZ"}]
        for i, valid_code in enumerate(valid_codes):
            with self.subTest(i=i):
                try:
                    prop._validate_holiday_code(valid_code)
                except err.InvalidHolidayCodeError:
                    self.fail("InvalidHolidayCodeError raised")
        for j, invalid_code in enumerate(invalid_codes):
            with (self.subTest(j=j),
                  self.assertRaises(err.InvalidHolidayCodeError)):
                prop._validate_holiday_code(invalid_code)

    def test___set__(self) -> None:
        prop = p.HolidayCodeProperty(self.dummy, "prop")
        values = [["", "BW"], ["DE", "BW"], ["de", "bw"],
                  ["DE", ""]]
        results = [(None, None), ("DE", "BW"), ("DE", "BW"),
                   ("DE", "")]
        for i, (value, result) in enumerate(zip(values, results, strict=True)):
            with self.subTest(i=i):
                prop.__set__(
                    self.dummy, {"country": value[0], "subdivision": value[1]})
                self.assertEqual(result, prop.__get__(self.dummy))


class TestPages(PropertyTestCase):
    def test__set_value(self) -> None:
        ...

    def test_page_ids(self) -> None:
        ...

    def test__set_pages(self) -> None:
        ...

    def test_page_num(self) -> None:
        ...

    def test_validate(self) -> None:
        ...


class TestPage(PropertyTestCase):
    def test___set__(self) -> None:
        ...


class TestRouteTypeProperty(PropertyTestCase):
    def get_property(self, name: str) -> p.RouteTypeProperty | None:
        return super().get_property(name)

    def test__validate_route_type(self) -> None:
        valid_values = ["Tram", "tram", "TRAM", "1", "2", "3", "11", "12"]
        invalid_values = ["tr a m", "test", "22"]
        for i, valid_value in enumerate(valid_values):
            with self.subTest(i=i):
                try:
                    p.RouteTypeProperty._validate_route_type(valid_value)
                except err.InvalidRouteTypeValueError:
                    self.fail("InvalidRouteTypeValueError raised")
        for j, invalid_value in enumerate(invalid_values):
            with (self.subTest(j=j),
                  self.assertRaises(err.InvalidRouteTypeValueError)):
                p.RouteTypeProperty._validate_route_type(invalid_value)

    def test___set__(self) -> None:
        prop = p.RouteTypeProperty(self.dummy, "prop")
        values = ["Tram", "tram", "bus", "Bus", "0", "2", "3", "5", "11", "12"]
        results = ["Tram", "Tram", "Bus", "Bus", "Tram", "Rail", "Bus",
                   "CableTram", "Trolleybus", "Monorail"]
        for i, (value, result) in enumerate(zip(values, results, strict=True)):
            with self.subTest(i=i):
                prop.__set__(self.dummy, value)
                self.assertEqual(result, prop.__get__(self.dummy))


class TestOutputPathProperty(PropertyTestCase):
    @classmethod
    def setUpClass(cls: P2GTestCase, **kwargs) -> None:
        kwargs["create_temp_dir"] = True
        super().setUpClass(**kwargs)

    def get_property(self, name: str) -> p.OutputPathProperty | None:
        return super().get_property(name)

    def test__validate_path(self) -> None:
        path = Path(self.temp_dir.name)
        existing_zip_path = path.joinpath("test_exists.zip")
        invalid_file_ending = path.joinpath("test.txt")
        # Create empty zip.
        for file_name in existing_zip_path, invalid_file_ending:
            with open(file_name, "w") as file:
                file.write("")
        non_existing_zip_path = path.joinpath("tests_new.zip")
        invalid_file_ending = path.joinpath("test.txt")

        valid_values = [path, non_existing_zip_path, existing_zip_path]
        invalid_values = [invalid_file_ending]
        for i, valid_value in enumerate(valid_values):
            with self.subTest(i=i):
                try:
                    p.OutputPathProperty._validate_path(valid_value)
                except err.InvalidOutputPathError:
                    self.fail("InvalidOutputPathError raised")
        for j, invalid_value in enumerate(invalid_values):
            with (self.subTest(j=j),
                  self.assertRaises(err.InvalidOutputPathError)):
                p.OutputPathProperty._validate_path(invalid_value)

    def test___set__(self) -> None:
        self.dummy.prop = p.OutputPathProperty(self.dummy, "prop")
        path = Path(self.temp_dir.name)
        zip_path = path.joinpath("test.zip")
        values = [str(path), zip_path, str(zip_path)]
        results = [path, zip_path, zip_path]
        for i, (value, result) in enumerate(zip(values, results, strict=True)):
            self.get_property("prop").__set__(self.dummy, value)
            self.assertEqual(result, self.dummy.prop)


class TestDateBoundsProperty(PropertyTestCase):
    def get_property(self, name: str) -> p.DateBoundsProperty | None:
        return super().get_property(name)

    def test_clean_value(self) -> None:
        valid_values = ["", ["", ""], ["20221004", ""], ["", "20221004"]]
        invalid_values = [[""], ["20220229", ""], ["202202", ""]]
        for i, valid_value in enumerate(valid_values):
            with self.subTest(i=i):
                try:
                    p.DateBoundsProperty.clean_value(valid_value)
                except err.InvalidDateBoundsError:
                    self.fail("InvalidDateBoundsError raised")
        for j, invalid_value in enumerate(invalid_values):
            with (self.subTest(j=j),
                  self.assertRaises(err.InvalidDateBoundsError)):
                p.DateBoundsProperty.clean_value(invalid_value)

    def test___set__(self) -> None:
        self.dummy.prop = p.DateBoundsProperty(self.dummy, "prop")
        values = ["", ["20220202", "20221010"]]
        for i, value in enumerate(values):
            with self.subTest(i=i):
                self.dummy.prop = value
                result = p.DateBoundsProperty.clean_value(value)
                self.assertEqual(result, self.dummy.prop)


class TestAbbrevProperty(PropertyTestCase):
    def get_property(self, name: str) -> p.AbbrevProperty | None:
        return super().get_property(name)

    def test_clean_value(self) -> None:
        values = {"hbf.": "hauptbahnhof", "bf.    ": "bahnhof",
                  "bf": "Bahnhof",
                  "longtest": "shorter", "ßhorttest": "longer  "}
        clean_values = {"sshorttest": "longer", "longtest": "shorter",
                        "hbf.": "hauptbahnhof", "bf.": "bahnhof",
                        "bf": "bahnhof"}
        self.assertEqual(clean_values, p.AbbrevProperty.clean_value(values))

    def test___set__(self) -> None:
        self.dummy.prop = p.AbbrevProperty(self.dummy, "prop")
        values = [{"a": "am", "aa": "aam"}, {},
                  {"hbf.": "hauptbahnhof", "bf.    ": "bahnhof",
                   "bf": "Bahnhof", "longtest": "shorter",
                   "ßhorttest": "longer  "}]
        for i, value in enumerate(values):
            with self.subTest(i=i):
                clean_value = p.AbbrevProperty.clean_value(value)
                self.get_property("prop").__set__(self.dummy, value)
                self.assertEqual(clean_value, self.dummy.prop)


class TestAverageSpeedProperty(PropertyTestCase):
    def get_property(self, name: str) -> p.AverageSpeedProperty | None:
        return super().get_property(name)

    def test___get__(self) -> None:
        self.dummy.prop = p.AverageSpeedProperty(self.dummy, "prop")
        # Default average speed depends on the route type,
        # but only if it is set to 0.
        self.dummy.prop = 0
        prop = self.get_property("prop")
        self.dummy.gtfs_routetype = "tram"
        self.assertEqual(25, prop.__get__(self.dummy))
        self.dummy.gtfs_routetype = "monorail"
        self.assertEqual(35, prop.__get__(self.dummy))
        for value in range(1, 201):
            self.dummy.prop = value
            self.assertEqual(value, prop.__get__(self.dummy))
