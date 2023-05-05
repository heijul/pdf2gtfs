from unittest import TestCase

from pdf2gtfs.config import Config
from pdf2gtfs.datastructures.table.fields import Field
from pdf2gtfs.datastructures.table.fieldtype import (
    ABS_FALLBACK, ABS_INDICATORS, false, field_has_type,
    field_has_type_wrapper, is_legend,
    is_repeat_value,
    is_time_data, is_wrapper, T, true,
    )


class AbsIndicatorTests(TestCase):
    def test_is_time_data(self) -> None:
        Config.time_format = "%H:%M"
        time_data = ["13:33", "03:12", "01:01"]
        non_time_data = ["", "a", "19:65", "13.33", "18: 42"]
        for t in time_data:
            with self.subTest(time_data=t):
                self.assertTrue(is_time_data(Field(t)))
        for t in non_time_data:
            with self.subTest(time_data=t):
                self.assertFalse(is_time_data(Field(t)))
        # Different format.
        Config.time_format = "%H.%M"
        for t in ["13.42", "03.2", "2.2"]:
            with self.subTest(time_data=t):
                self.assertTrue(is_time_data(Field(t)))

    def test_is_wrapper(self) -> None:
        f = Field("Test")
        self.assertTrue(is_wrapper("test")(f))
        self.assertFalse(is_wrapper("aa", "te st", "test ")(f))

    def test_true(self) -> None:
        self.assertTrue(true(True))
        self.assertTrue(true(False))
        self.assertTrue(true(False, True, False))

    def test_false(self) -> None:
        self.assertFalse(false(True))
        self.assertFalse(false(False))
        self.assertFalse(false(True, True, False))

    def test_is_repeat_value(self) -> None:
        self.assertTrue(is_repeat_value(Field("5")))
        self.assertTrue(is_repeat_value(Field("5 ")))
        self.assertTrue(is_repeat_value(Field("3-8")))
        self.assertTrue(is_repeat_value(Field("3 -8")))
        self.assertTrue(is_repeat_value(Field("3- 8")))
        self.assertTrue(is_repeat_value(Field("3,5")))
        self.assertTrue(is_repeat_value(Field("3, 5")))

        self.assertFalse(is_repeat_value(Field("")))
        self.assertFalse(is_repeat_value(Field(" ")))
        self.assertFalse(is_repeat_value(Field("3-7 min")))
        self.assertFalse(is_repeat_value(Field("3 min")))
        self.assertFalse(is_repeat_value(Field("-1")))
        self.assertFalse(is_repeat_value(Field("3,")))
        self.assertFalse(is_repeat_value(Field("3.")))
        # TODO: These are True/False but should probably be False/True.
        self.assertTrue(is_repeat_value(Field("   3 - 8     ")))
        self.assertFalse(is_repeat_value(Field("3  -8")))

    def test_is_legend(self) -> None:
        self.assertTrue(is_legend(Field("a=3")))
        self.assertTrue(is_legend(Field("foobar =barfoo")))
        self.assertTrue(is_legend(Field("foobar= barfoo")))
        self.assertTrue(is_legend(Field("foobar :barfoo")))
        self.assertTrue(is_legend(Field("foobar: barfoo")))
        self.assertTrue(is_legend(Field("13:33")))
        self.assertTrue(is_legend(Field("25:332")))

        self.assertFalse(is_legend(Field("")))
        self.assertFalse(is_legend(Field("test")))
        self.assertFalse(is_legend(Field("foo bar")))
        # TODO: These may need adjustments.
        self.assertTrue(is_legend(Field("25: =3")))
        self.assertTrue(is_legend(Field("25:=3")))


class RelIndicatorTests(TestCase):
    def test_field_has_type(self) -> None:
        f = Field("test")
        f.type.possible_types = {T.Data: 1, T.Other: 0.3}
        self.assertTrue(field_has_type(f, T.Data, True))
        self.assertTrue(field_has_type(f, T.Data, False))
        self.assertTrue(field_has_type(f, T.Other, False))
        self.assertFalse(field_has_type(f, T.Other, True))
        self.assertFalse(field_has_type(f, T.Days, True))
        self.assertFalse(field_has_type(f, T.Days, False))
        f.type.inferred_type = T.Stop
        self.assertFalse(field_has_type(f, T.Data, True))
        self.assertTrue(field_has_type(f, T.Data, False))
        self.assertTrue(field_has_type(f, T.Stop, True))

    def test_field_has_type_wrapper(self) -> None:
        # Possible types are in ABS_FALLBACK
        f = Field("test")
        f.get_type()
        for t in ABS_FALLBACK + list(ABS_INDICATORS.keys()):
            with self.subTest(fieldtype=t):
                self.assertEqual(field_has_type(f, t),
                                 field_has_type_wrapper(t)(f))


class TestFieldType(TestCase):
    def test_guess_type(self) -> None:
        f = Field("")
        self.assertEqual(T.Other, f.type.guess_type())
        self.assertEqual(T.Other, f.type.guess_type())
        Config.time_format = "%H.%M"
        f = Field("09.33")
        self.assertEqual(T.Data, f.type.guess_type())
        self.assertDictEqual({T.Data: 0.667, T.Other: 0.333},
                             f.type.possible_types)
