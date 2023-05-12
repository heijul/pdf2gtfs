from itertools import pairwise
from operator import attrgetter, methodcaller
from unittest import TestCase

from more_itertools import collapse, first_true

from pdf2gtfs.config import Config
from pdf2gtfs.datastructures.pdftable.bbox import BBox
from pdf2gtfs.datastructures.table.direction import E, H, N, S, V, W
from pdf2gtfs.datastructures.table.cell import Cell
from pdf2gtfs.datastructures.table.celltype import T
from pdf2gtfs.datastructures.table.table import Table
from pdf2gtfs.reader import (
    assign_other_cells_to_tables,
    get_cells_from_page, Reader,
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
    def _create_tables(data_cells, other_cells) -> list[Table]:
        t = Table.from_data_cells(data_cells)
        t.insert_repeat_cells(other_cells)
        tables = t.max_split(other_cells)
        assign_other_cells_to_tables(tables, other_cells)
        return tables

    def setUp(self) -> None:
        self.f_data, self.f_other, _ = get_cells_from_page(self.page)
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
        self.multi_idx = [(self.idx[i], self.idx[i + 2]) for i in range(1)]

    def test_bbox(self) -> None:
        table, *_ = self._create_tables(self.f_data, self.f_other)
        table_bbox: BBox = table.bbox
        for row_cell in table.top.row:
            for cell in row_cell.col:
                cell: Cell
                table_bbox.is_h_overlap(cell.bbox, 1)
                table_bbox.is_v_overlap(cell.bbox, 1)
        # TODO: Needs more tests.

    def test_from_cells(self) -> None:
        # First table
        f_data = sorted(self.f_data, key=attrgetter("bbox.y0",
                                                    "bbox.x0"))[:self.idx[1]]
        f_data = sorted(f_data, key=attrgetter("bbox.x0"))
        f1 = first_true(f_data, pred=lambda x: x.text == "21.02").duplicate()
        f2 = first_true(f_data, pred=lambda x: x.text == "21.03").duplicate()
        f1.below = f2
        t2 = Table(f1, f2)
        assign_other_cells_to_tables([t2], f_data[2:])
        while t2.expand(S):
            pass
        while t2.expand(E):
            pass
        t1 = Table.from_data_cells(f_data)
        for cf1, cf2 in zip(t1.top.row, t2.top.row, strict=True):
            for cell1, cell2 in zip(cf1.col, cf2.col, strict=True):
                self.assertEqual(cell1.text, cell2.text)
                self.assertEqual(cell1.bbox, cell2.bbox)

    def test_get_empty_cell_bbox(self) -> None:
        table, *_ = self._create_tables(self.f_data, self.f_other)
        empty_cells = collapse(table.of_type(T.Empty))
        # TODO: Check this also works in case the table is expanded.
        # TODO: Check that no other cell is overlapping (only for datacells).
        for empty_cell in empty_cells:
            empty_cell: Cell
            for row_cell in empty_cell.row:
                row_cell: Cell
                row_cell.is_overlap(V, empty_cell, 1)
            for col_cell in empty_cell.col:
                col_cell: Cell
                col_cell.is_overlap(H, empty_cell, 1)

    def test_expand(self) -> None:
        table, *_ = self._create_tables(self.f_data, self.f_other)
        self.assertTrue(table.expand(W))
        # Column left of data contains only stop annots.
        col = list(table.left.col)
        self.assertEqual(23, len(col))
        stop_annots = 0
        for cell in col:
            is_empty = cell.has_type(T.Empty)
            is_stop_annot = cell.get_type() == T.StopAnnot
            if is_stop_annot:
                stop_annots += 1
            self.assertTrue(is_empty or is_stop_annot)
        self.assertEqual(4, stop_annots)
        # No cells right of the table
        self.assertFalse(table.expand(E))
        # Column left of stop annots contains stops.
        self.assertTrue(table.expand(W))
        # Need to infer types for the stops.
        table.infer_cell_types(None)
        stops = list(table.left.col)
        for stop in stops:
            self.assertTrue(stop.get_type() == T.Stop)
        self.assertEqual(23, len(stops))
        # Can not expand further in W.
        self.assertFalse(table.expand(W))
        # TODO: These should be tested further.
        self.assertTrue(table.expand(S))
        self.assertFalse(table.expand(S))
        self.assertTrue(table.expand(N))
        self.assertTrue(table.expand(N))
        self.assertTrue(table.expand(N))
        self.assertFalse(table.expand(N))

    def test_get_contained_cells__none(self) -> None:
        table, *_ = self._create_tables(self.f_data, self.f_other)
        # Repeat cells are already added.
        self.assertListEqual([],
                             table.get_contained_cells(table.potential_cells))

    def test_get_contained_cells__single(self) -> None:
        # Each table separately.
        cell_counts = [3, 3, 6]
        cell_texts = [["alle", "30", "Min."],
                      ["alle", "15", "Min."],
                      ["alle", "10", "15", "Min."]]
        f_data = sorted(self.f_data, key=attrgetter("bbox.y0"))
        for i, (low, high) in enumerate(pairwise(self.idx)):
            with self.subTest(table_number=i, low=low, high=high):
                table_data = f_data[low:high]
                table = Table.from_data_cells(table_data)
                cells = table.get_contained_cells(self.f_other)
                self.assertEqual(cell_counts[i], len(cells))
                table_bbox = table.bbox
                for cell in cells:
                    self.assertTrue(table_bbox.is_h_overlap(cell.bbox, 1))
                    self.assertTrue(table_bbox.is_v_overlap(cell.bbox, 1))
                    self.assertIn(cell.text, cell_texts[i])

    def test_get_contained_cells__multi(self) -> None:
        # Multiple consecutive tables.
        cell_counts = [7, 12]
        cell_texts = [["alle", "alle", "15", "30", "Min.", "Min.",
                       "Sonn- und Feiertag"],
                      ["alle", "alle", "alle", "10", "15", "15", "Min.",
                       "Min.", "Min.", "Sonn- und Feiertag", "V", "V"]]
        f_data = sorted(self.f_data, key=attrgetter("bbox.y0"))
        for i, (low, high) in enumerate(pairwise(self.multi_idx)):
            with self.subTest(table_number=i, low=low, high=high):
                table_data = f_data[low:high]
                table = Table.from_data_cells(table_data)
                cells = table.get_contained_cells(self.f_other)
                self.assertEqual(cell_counts[i], len(cells))
                table_bbox = table.bbox
                for cell in cells:
                    self.assertTrue(table_bbox.is_h_overlap(cell.bbox, 1))
                    self.assertTrue(table_bbox.is_v_overlap(cell.bbox, 1))
                    self.assertIn(cell.text, cell_texts[i])
                self.assertListEqual(sorted(cell_texts[i]),
                                     sorted([f.text for f in cells]))

    def test_get_contained_cells__all(self) -> None:
        f_data = sorted(self.f_data, key=attrgetter("bbox.y0"))
        # All tables as one.
        table_data = f_data[self.idx[0]:self.idx[-1]]
        table = Table.from_data_cells(table_data)
        cells = table.get_contained_cells(self.f_other)
        self.assertEqual(16, len(cells))
        table_bbox = table.bbox
        cell_texts = ["alle", "10", "15", "30", "Min.",
                      "V", "*", "Sonn- und Feiertag"]
        for cell in cells:
            self.assertTrue(table_bbox.is_h_overlap(cell.bbox, 1))
            self.assertTrue(table_bbox.is_v_overlap(cell.bbox, 1))
            self.assertIn(cell.text, cell_texts)

    def test_get_containing_col(self) -> None:
        table, *_ = self._create_tables(self.f_data, self.f_other)
        for col in [f.col for f in table.top.row]:
            col = list(col)
            with self.subTest(col=col):
                for cell in col:
                    self.assertListEqual(col, table.get_containing_col(cell))

    def test_get_col_left_of__existing_cells(self) -> None:
        table, *_ = self._create_tables(self.f_data, self.f_other)
        cols = map(list, map(methodcaller("iter", S), table.get_list(H)))
        for i, (col1, col2) in enumerate(pairwise(cols)):
            col1: list[Cell] = list(col1)
            col2: list[Cell] = list(col2)
            with self.subTest(i=i):
                left_col = list(table.get_col_left_of(col2[0]))
                self.assertListEqual(col1, left_col)

    def test_get_col_left_of__new_cell(self) -> None:
        left_cols_idx = [[13, 13, 13], [13, 13, 13], [2, 2, 2, 9, 9, 9]]
        for i, (low, high) in enumerate(pairwise(self.idx)):
            table = Table.from_data_cells(self.f_data[low:high])
            contained_cells = table.get_contained_cells(self.f_other)
            contained_cells.sort(key=attrgetter("bbox.x0"))
            with self.subTest(i=i):
                for col_id, col in enumerate(map(table.get_col_left_of,
                                                 contained_cells)):
                    idx = left_cols_idx[i][col_id]
                    table_col = table.get_list(H)[idx].col
                    self.assertListEqual(list(table_col), list(col))

    def test_get_repeat_identifiers(self) -> None:
        table = Table.from_data_cells(self.f_data)
        repeat_idents = table.get_repeat_identifiers(self.f_other)
        self.assertEqual(8, len(repeat_idents))
        for ident in repeat_idents:
            self.assertIn(ident.text, ["alle", "Min."])

    def test_get_repeat_values(self) -> None:
        table = Table.from_data_cells(self.f_data)
        repeat_idents = table.get_repeat_identifiers(self.f_other)
        repeat_values = table.get_repeat_values(repeat_idents, self.f_other)
        self.assertEqual(4, len(repeat_values))
        for value in repeat_values:
            self.assertIn(value.text, ["10", "15", "30"])

    def test_split_at_cells__horizontally(self) -> None:
        tables1 = self._create_tables([f.duplicate() for f in self.f_data],
                                      [f.duplicate() for f in self.f_other])
        table = Table.from_data_cells(self.f_data)
        assign_other_cells_to_tables([table], self.f_other)
        table.insert_repeat_cells(table.potential_cells)
        contained_cells = table.get_contained_cells(table.potential_cells)
        tables2 = table.split_at_cells(H, contained_cells)
        for table1, table2 in zip(tables1, tables2, strict=True):
            cols1 = [f.col for f in table1.top.row]
            cols2 = [f.col for f in table2.top.row]
            for col1, col2 in zip(cols1, cols2, strict=True):
                self.assertListEqual([f.text for f in col1],
                                     [f.text for f in col2])

    def test_split_at_cells__vertically(self) -> None:
        lengths = [2, 2, 3]
        col_counts = [[14, 5], [14, 5], [3, 7, 5]]
        for i, (low, high) in enumerate(pairwise(self.idx)):
            table = Table.from_data_cells(self.f_data[low:high])
            contained_cells = table.get_contained_cells(self.f_other)
            with self.subTest(i=i):
                tables = table.split_at_cells(V, contained_cells)
                self.assertEqual(lengths[i], len(tables))
                for table_id, table in enumerate(tables):
                    self.assertEqual(col_counts[i][table_id],
                                     len(list(table.top.row)))

    def test_get_splitting_cols__empty(self) -> None:
        tables = self._create_tables(self.f_data, self.f_other)
        for table in tables:
            cells = table.get_contained_cells(table.potential_cells)
            cols = table.get_splitting_cols(cells)
            self.assertEqual(0, len(cols))

    def test_get_splitting_cols__single(self) -> None:
        expected_texts = [[["alle", "30", "Min."]],
                          [["alle", "15", "Min."]],
                          [["alle", "10", "Min."], ["alle", "15", "Min."]]]

        f_data = sorted(self.f_data, key=attrgetter("bbox.y0"))
        for i, (low, high) in enumerate(pairwise(self.idx)):
            with self.subTest(table_number=i, low=low, high=high):
                table_data = f_data[low:high]
                table = Table.from_data_cells(table_data)
                assign_other_cells_to_tables([table], self.f_other)
                cells = table.get_contained_cells(table.potential_cells)
                cols = table.get_splitting_cols(cells)
                for col_id, col in enumerate(cols):
                    texts = [f.text for f in col if f.get_type() != T.Empty]
                    self.assertListEqual(expected_texts[i][col_id], texts)

    def test_get_splitting_cols__multi(self) -> None:
        expected_texts = [[["alle", "30", "Min.", "alle", "15", "Min."]], []]
        f_data = sorted(self.f_data, key=attrgetter("bbox.y0"))
        for i, (low, high) in enumerate(pairwise(self.multi_idx)):
            with self.subTest(table_number=i, low=low, high=high):
                table_data = f_data[low:high]
                table = Table.from_data_cells(table_data)
                assign_other_cells_to_tables([table], self.f_other)
                cells = table.get_contained_cells(table.potential_cells)
                cols = table.get_splitting_cols(cells)
                self.assertEqual(len(expected_texts[i]), len(cols))
                for col_id, col in enumerate(cols):
                    texts = [f.text for f in col if f.get_type() != T.Empty]
                    self.assertListEqual(expected_texts[i][col_id], texts)

    def test_get_splitting_cols__all(self) -> None:
        f_data = sorted(self.f_data, key=attrgetter("bbox.y0"))
        table = Table.from_data_cells(f_data)
        assign_other_cells_to_tables([table], self.f_other)
        cells = table.get_contained_cells(table.potential_cells)
        cols = table.get_splitting_cols(cells)
        self.assertEqual(0, len(cols))

    def test_get_splitting_rows__empty(self) -> None:
        tables = self._create_tables(self.f_data, self.f_other)
        for table in tables:
            cells = table.get_contained_cells(table.potential_cells)
            rows = table.get_splitting_rows(cells)
            self.assertEqual(0, len(rows))

    def test_get_splitting_rows__single(self) -> None:
        f_data = sorted(self.f_data, key=attrgetter("bbox.y0"))
        for i, (low, high) in enumerate(pairwise(self.idx)):
            with self.subTest(table_number=i, low=low, high=high):
                table_data = f_data[low:high]
                table = Table.from_data_cells(table_data)
                assign_other_cells_to_tables([table], self.f_other)
                cells = table.get_contained_cells(table.potential_cells)
                rows = table.get_splitting_rows(cells)
                self.assertEqual(0, len(rows))

    def test_get_splitting_rows__multi(self) -> None:
        expected_texts = [[["Sonn- und Feiertag"]], [["Sonn- und Feiertag"]]]
        f_data = sorted(self.f_data, key=attrgetter("bbox.y0"))
        for i, (low, high) in enumerate(pairwise(self.multi_idx)):
            with self.subTest(table_number=i, low=low, high=high):
                table_data = f_data[low:high]
                table = Table.from_data_cells(table_data)
                assign_other_cells_to_tables([table], self.f_other)
                cells = table.get_contained_cells(table.potential_cells)
                rows = table.get_splitting_rows(cells)
                self.assertEqual(len(expected_texts[i]), len(rows))
                for row_id, row in enumerate(rows):
                    texts = [f.text for f in row if f.get_type() != T.Empty]
                    self.assertListEqual(expected_texts[i][row_id], texts)

    def test_get_splitting_rows__all(self) -> None:
        f_data = sorted(self.f_data, key=attrgetter("bbox.y0"))
        table = Table.from_data_cells(f_data)
        assign_other_cells_to_tables([table], self.f_other)
        cells = table.get_contained_cells(table.potential_cells)
        rows = table.get_splitting_rows(cells)
        self.assertEqual(3, len(rows))
        self.assertListEqual(
            [["Sonn- und Feiertag"], ["Sonn- und Feiertag"], ["V", "V"]],
            [[f.text for f in row] for row in rows])

    def test_max_split(self) -> None:
        self.skipTest("Not implemented yet!")

    def test_remove_empty_series(self) -> None:
        self.skipTest("Not implemented yet!")

    def test_to_timetable(self) -> None:
        self.skipTest("Not implemented yet!")

    def test_find_stops(self) -> None:
        self.skipTest("Not implemented yet!")

    def test_expand_all(self) -> None:
        self.skipTest("Not implemented yet!")

    def test_infer_cell_types(self) -> None:
        self.skipTest("Not implemented yet!")

    def test_of_type(self) -> None:
        self.skipTest("Not implemented yet!")

    def test_merge_series(self) -> None:
        self.skipTest("Not implemented yet!")

    def test_merge_stops(self) -> None:
        self.skipTest("Not implemented yet!")

    def test_get_end_node(self) -> None:
        self.skipTest("Not implemented yet!")

    def test_set_end_node(self) -> None:
        self.skipTest("Not implemented yet!")

    def test_update_end_node(self) -> None:
        self.skipTest("Not implemented yet!")

    def test_get_first(self) -> None:
        self.skipTest("Not implemented yet!")

    def test_get_list(self) -> None:
        self.skipTest("Not implemented yet!")

    def test_from_objects(self) -> None:
        self.skipTest("Check if used.")

    def test_insert(self) -> None:
        self.skipTest("Not implemented yet!")

    def test_get_series(self) -> None:
        self.skipTest("Not implemented yet!")

    def test_get_bbox_of(self) -> None:
        self.skipTest("Not implemented yet!")

    def test_iter(self) -> None:
        self.skipTest("Not implemented yet!")
