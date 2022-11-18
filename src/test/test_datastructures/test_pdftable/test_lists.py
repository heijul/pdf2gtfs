from datastructures.pdftable.container import Row
from test import P2GTestCase


class TestRowList(P2GTestCase):
    def setUp(self) -> None:
        from datastructures.pdftable.pdftable import PDFTable
        from datastructures.pdftable.lists import RowList

        self.table = PDFTable()
        self.rowlist = RowList(self.table)

    def test_empty(self) -> None:
        self.assertTrue(self.rowlist.empty)
        row = Row(self.table)
        self.rowlist.add(row)
        self.assertFalse(self.rowlist.empty)

    def test_add(self) -> None:
        self.assertTrue(self.rowlist.empty)
        row = Row()
        self.assertIsNone(row.table)
        self.rowlist.add(row)
        self.assertTrue(1, len(self.rowlist.objects))
        self.assertEqual(self.table, row.table)

    def test__get_neighbor(self) -> None:
        ...

    def test_prev(self) -> None:
        ...

    def test_next(self) -> None:
        ...

    def test_index(self) -> None:
        ...

    def test_from_list(self) -> None:
        from datastructures.pdftable.lists import RowList

        rows = [Row(), Row(), Row()]
        rowlist = RowList.from_list(self.table, rows)
        self.assertEqual(rows, list(rowlist.objects))
        self.assertEqual(self.table, rowlist.table)

    def test_of_type(self) -> None:
        ...

    def test_of_types(self) -> None:
        ...

    def test_mean_row_field_count(self) -> None:
        ...

    def test_merge(self) -> None:
        ...
