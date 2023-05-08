from itertools import pairwise
from operator import attrgetter
from unittest import TestCase

from more_itertools import collapse, first_true

from pdf2gtfs.config import Config
from pdf2gtfs.datastructures.pdftable.bbox import BBox
from pdf2gtfs.datastructures.table.direction import E, H, N, S, V, W
from pdf2gtfs.datastructures.table.fields import Field
from pdf2gtfs.datastructures.table.fieldtype import T
from pdf2gtfs.datastructures.table.table import Table
from pdf2gtfs.reader import (
    assign_other_fields_to_tables,
    get_fields_from_page, Reader,
    )

from test import TEST_DATA_DIR


class TestTable(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        Config.pages = "3"
        Config.filename = str(TEST_DATA_DIR.joinpath("vag_1_preprocessed.pdf"))
        # No need to preprocess or check for valid pages.
        reader = Reader()
        cls.page = next(reader.get_pages())

    @staticmethod
    def _create_tables(data_fields, other_fields) -> list[Table]:
        t = Table.from_fields(data_fields)
        t.insert_repeat_fields(other_fields)
        tables = t.max_split(other_fields)
        assign_other_fields_to_tables(tables, other_fields)
        return tables

    def setUp(self) -> None:
        self.f_data, self.f_other, _ = get_fields_from_page(self.page)
        f_data = sorted(self.f_data, key=attrgetter("bbox.y0"))
        self.idx = [0]
        for i, (left, right) in enumerate(pairwise(f_data)):
            # Same line.
            if abs(left.bbox.y0 - right.bbox.y0) < 3:
                continue
            # Too much distance -> new table.
            if abs(left.bbox.y1 - right.bbox.y0) > 3:
                self.idx.append(i + 1)
        self.assertEqual(3, len(self.idx))
        # End of the last table.
        self.idx.append(len(f_data))

    def test_bbox(self) -> None:
        table, *_ = self._create_tables(self.f_data, self.f_other)
        table_bbox: BBox = table.bbox
        for col_start in table.get_list(H):
            col = table.get_list(V, col_start)
            for field in col:
                field: Field
                table_bbox.is_h_overlap(field.bbox, 1)
                table_bbox.is_v_overlap(field.bbox, 1)
        # TODO: Needs more tests.

    def test_from_fields(self) -> None:
        # First table
        f_data = sorted(self.f_data, key=attrgetter("bbox.y0",
                                                    "bbox.x0"))[:self.idx[1]]
        f_data = sorted(f_data, key=attrgetter("bbox.x0"))
        f1 = first_true(f_data, pred=lambda x: x.text == "21.02").duplicate()
        f2 = first_true(f_data, pred=lambda x: x.text == "21.03").duplicate()
        f1.below = f2
        t2 = Table(f1, f2)
        assign_other_fields_to_tables([t2], f_data[2:])
        while t2.expand(S):
            pass
        while t2.expand(E):
            pass
        # t2.expand_all(True)
        t1 = Table.from_fields(f_data)
        for cf1, cf2 in zip(t1.get_list(H), t2.get_list(H), strict=True):
            col1 = t1.get_list(V, cf1)
            col2 = t2.get_list(V, cf2)
            for field1, field2 in zip(col1, col2, strict=True):
                self.assertEqual(field1.text, field2.text)
                self.assertEqual(field1.bbox, field2.bbox)

    def test_get_empty_field_bbox(self) -> None:
        table, *_ = self._create_tables(self.f_data, self.f_other)
        empty_fields = collapse(table.of_type(T.Empty))
        # TODO: Check this also works in case the table is expanded.
        # TODO: Check that no other field is overlapping (only for datafields).
        for empty_field in empty_fields:
            empty_field: Field
            for field in table.get_list(H, empty_field):
                field: Field
                field.is_overlap(V, empty_field, 1)
            for field in table.get_list(V, empty_field):
                field: Field
                field.is_overlap(H, empty_field, 1)

    def test_expand(self) -> None:
        table, *_ = self._create_tables(self.f_data, self.f_other)
        self.assertTrue(table.expand(W))
        # Column left of data contains only stop annots.
        col = table.get_list(V, table.left)
        self.assertEqual(23, len(col))
        stop_annots = 0
        for field in col:
            is_empty = field.has_type(T.Empty)
            is_stop_annot = field.get_type() == T.StopAnnot
            if is_stop_annot:
                stop_annots += 1
            self.assertTrue(is_empty or is_stop_annot)
        self.assertEqual(4, stop_annots)
        # No fields right of the table
        self.assertFalse(table.expand(E))
        # Column left of stop annots contains stops.
        self.assertTrue(table.expand(W))
        # Need to infer types for the stops.
        table.infer_field_types(None)
        stops = table.get_list(V, table.left)
        for stop in stops:
            self.assertTrue(stop.get_type() == T.Stop)
        self.assertEqual(23, len(stops))
        # Can not expand further in W.
        self.assertFalse(table.expand(W))
        # TODO: These should be tested further.
        self.assertTrue(table.expand(S))
        self.assertTrue(table.expand(S))
        self.assertFalse(table.expand(S))
        self.assertTrue(table.expand(N))
        self.assertTrue(table.expand(N))
        self.assertTrue(table.expand(N))
        self.assertFalse(table.expand(N))

    def test_get_contained_fields__none(self) -> None:
        table, *_ = self._create_tables(self.f_data, self.f_other)
        # Repeat fields are already added.
        self.assertListEqual([],
                             table.get_contained_fields(table.other_fields))

    def test_get_contained_fields__some(self) -> None:
        # Each table separately.
        field_counts = [3, 3, 6]
        field_texts = [["alle", "30", "Min."],
                       ["alle", "15", "Min."],
                       ["alle", "10", "15", "Min."]]
        f_data = sorted(self.f_data, key=attrgetter("bbox.y0"))
        for i, (low, high) in enumerate(pairwise(self.idx)):
            with self.subTest(table_number=i, low=low, high=high):
                table_data = f_data[low:high]
                table = Table.from_fields(table_data)
                fields = table.get_contained_fields(self.f_other)
                self.assertEqual(field_counts[i], len(fields))
                table_bbox = table.bbox
                for field in fields:
                    self.assertTrue(table_bbox.is_h_overlap(field.bbox, 1))
                    self.assertTrue(table_bbox.is_v_overlap(field.bbox, 1))
                    self.assertIn(field.text, field_texts[i])

    def test_get_contained_fields__all(self) -> None:
        f_data = sorted(self.f_data, key=attrgetter("bbox.y0"))
        # All tables as one.
        table_data = f_data[self.idx[0]:self.idx[-1]]
        table = Table.from_fields(table_data)
        fields = table.get_contained_fields(self.f_other)
        self.assertEqual(16, len(fields))
        table_bbox = table.bbox
        field_texts = ["alle", "10", "15", "30", "Min.",
                       "V", "*", "Sonn- und Feiertag"]
        for field in fields:
            self.assertTrue(table_bbox.is_h_overlap(field.bbox, 1))
            self.assertTrue(table_bbox.is_v_overlap(field.bbox, 1))
            self.assertIn(field.text, field_texts)

