from unittest import TestCase

from pdf2gtfs.config import Config
from pdf2gtfs.datastructures.table.direction import W
from pdf2gtfs.datastructures.table.fields import EmptyField, Field, Fs
from pdf2gtfs.datastructures.table.fieldtype import (
    ABS_FALLBACK, ABS_INDICATORS, false, field_col_contains_type,
    field_has_type,
    field_has_type_wrapper, field_is_between_type, field_neighbor_has_type,
    field_neighbor_has_type_wrapper, field_row_contains_type,
    is_legend,
    is_repeat_value,
    is_time_data, is_wrapper, T, true,
    )
from pdf2gtfs.datastructures.table.table import Table


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

    def test_field_row_contains_type(self) -> None:
        f = Field("a")
        f.next = Field("b")
        f.next.next = Field("c")
        f.type.possible_types = {a: 0.1 for a in ABS_FALLBACK}
        f.next.type.possible_types = {
            T.StopAnnot: 0.333, T.DataAnnot: 0.1, T.Other: 0.333}
        f.next.next.type.possible_types = {T.Data: 0.667, T.Other: 0.333}
        Table(f, f.next.next)
        self.assertTrue(field_row_contains_type(f, T.Data))
        # Strict type checking.
        self.assertFalse(field_row_contains_type(f, T.Other))
        self.assertFalse(field_row_contains_type(f, T.DataAnnot))

        self.assertFalse(field_row_contains_type(f, T.LegendIdent))
        self.assertFalse(field_row_contains_type(f, T.Empty))

    def test_field_col_contains_type(self) -> None:
        f = Field("a")
        f.below = Field("b")
        f.below.below = Field("c")
        f.type.possible_types = {a: 0.1 for a in ABS_FALLBACK}
        f.below.type.possible_types = {
            T.StopAnnot: 0.333, T.DataAnnot: 0.1, T.Other: 0.333}
        f.below.below.type.possible_types = {T.Data: 0.667, T.Other: 0.333}
        Table(f, f.below.below)
        self.assertTrue(field_col_contains_type(f, T.Data))
        # Strict type checking.
        self.assertFalse(field_col_contains_type(f, T.Other))
        self.assertFalse(field_col_contains_type(f, T.DataAnnot))

        self.assertFalse(field_col_contains_type(f, T.LegendIdent))
        self.assertFalse(field_col_contains_type(f, T.Empty))

    def test_field_neighbor_has_type(self) -> None:
        a, b, c, d, e = create_fields(5)
        a.type.possible_types = {T.Stop: 1}
        b.type.possible_types = {T.StopAnnot: 1}
        c.type.possible_types = {T.Data: 1}
        d.type.possible_types = {T.DataAnnot: 1}
        e.type.possible_types = {T.Other: 1}
        b.prev = a
        b.next = c
        b.above = d
        b.below = e
        for typ in [T.Stop, T.Other, T.Data, T.DataAnnot]:
            with self.subTest(type=typ):
                self.assertTrue(
                    field_neighbor_has_type(b, typ, direct_neighbor=True))
        self.assertTrue(field_neighbor_has_type(b, T.Stop, True, [W]))
        self.assertFalse(field_neighbor_has_type(b, T.LegendIdent, True))
        self.assertTrue(field_neighbor_has_type(a, T.StopAnnot))
        b.next = EmptyField()
        self.assertEqual(c, b.next.next)
        self.assertFalse(field_neighbor_has_type(b, T.Data, True))
        self.assertTrue(field_neighbor_has_type(b, T.Data, False))

    def test_field_neighbor_has_type_wrapper(self) -> None:
        a, b, c, d, e = create_fields(5)
        a.type.possible_types = {T.Stop: 1}
        b.type.possible_types = {T.StopAnnot: 1}
        c.type.possible_types = {T.Other: 1}
        d.type.possible_types = {T.DataAnnot: 1}
        e.type.possible_types = {T.Data: 1}
        b.prev = a
        b.next = c
        b.above = d
        b.below = e
        for typ in ABS_FALLBACK + list(ABS_INDICATORS.keys()):
            with self.subTest(fieldtype=typ):
                self.assertEqual(field_neighbor_has_type(b, typ),
                                 field_neighbor_has_type_wrapper(typ)(b))

    def test_field_is_between_type(self) -> None:
        a, b, c, d, e = create_fields(5)
        a.type.possible_types = {T.RepeatIdent: 1}
        b.type.possible_types = {T.RepeatValue: 1}
        c.type.possible_types = {T.RepeatIdent: 1}
        d.type.possible_types = {T.Data: 1}
        e.type.possible_types = {T.Data: 1}
        b.prev = a
        b.next = c
        b.above = d
        b.below = e
        self.assertTrue(field_is_between_type(b, T.RepeatIdent))
        self.assertTrue(field_is_between_type(b, T.Data))
        c.type.possible_types = {T.Data: 1}
        self.assertFalse(field_is_between_type(b, T.RepeatIdent))
        b.below = EmptyField()
        self.assertFalse(field_is_between_type(b, T.Data))

    def test_rel_multiple_function_wrapper(self) -> None:
        self.skipTest("Check usage first!")


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


def create_fields(num: int) -> Fs:
    return [Field(chr(97 + i)) for i in range(num)]
