from config import Config
from datastructures.pdftable.bbox import BBox
from datastructures.pdftable.container import Column, Row
from datastructures.pdftable.enums import RowType
from datastructures.pdftable.field import Field
from datastructures.pdftable.pdftable import PDFTable
from test import P2GTestCase


class TestFieldContainer(P2GTestCase):
    def test_fields(self) -> None:
        ...

    def test_table(self) -> None:
        ...

    def test_has_type(self) -> None:
        ...

    def test_add_reference_to_field(self) -> None:
        ...

    def test_add_field(self) -> None:
        ...

    def test__add_field_at_index(self) -> None:
        ...

    def test_remove_field(self) -> None:
        ...

    def test_set_bbox_from_fields(self) -> None:
        ...

    def test__add_field(self) -> None:
        ...

    def test__contains_time_data(self) -> None:
        ...

    def test__split_at(self) -> None:
        ...

    def test_has_field_of_type(self) -> None:
        ...


def create_fields(num_x: int, num_y: int, delta_x: int, delta_y: int
                  ) -> list[Field]:
    x = 103.12
    y = 44.213
    fields = []
    for i in range(num_y):
        for j in range(num_x):
            cur_y = y + i * delta_y
            cur_x = x + j * delta_x
            bbox = BBox(cur_x, cur_y, cur_x + delta_x, cur_y + delta_y)
            fields.append(Field(bbox, f"f_{j}_{i}"))
    return fields


class TestRow(P2GTestCase):
    def test_from_fields(self) -> None:
        fields = create_fields(7, 1, 12, 7)
        row = Row.from_fields(fields)
        self.assertEqual(fields, row.fields)
        bbox = BBox(fields[0].bbox.x0, fields[0].bbox.y0,
                    fields[-1].bbox.x1, fields[0].bbox.y1)
        self.assertEqual(bbox, row.bbox)

    def test_add_field(self) -> None:
        fields1 = create_fields(7, 1, 12, 7)
        fields2 = create_fields(7, 1, 12, 7)
        row = Row.from_fields(fields1)
        row2 = Row()
        for field in list(fields2):
            row2.add_field(field)
        self.assertListEqual([f.bbox for f in row2.fields],
                             [f.bbox for f in row.fields])
        self.assertListEqual([f.text for f in row2.fields],
                             [f.text for f in row.fields])

    def test_type(self) -> None:
        fields = create_fields(7, 1, 12, 7)
        row = Row.from_fields(fields)
        self.assertFalse(row.has_type())
        self.assertEqual(RowType.OTHER, row.type)
        Config.time_format = "%H.%M"
        row.fields[0].text = "03.55"
        self.assertEqual(RowType.OTHER, row.type)
        row.update_type()
        self.assertEqual(RowType.DATA, row.type)
        self.assertTrue(row.has_type())

    def test_update_type(self) -> None:
        fields = create_fields(7, 1, 12, 7)
        row = Row.from_fields(fields)
        self.assertFalse(row.has_type())
        row.update_type()
        self.assertTrue(row.has_type())
        self.assertEqual(RowType.OTHER, row.type)
        Config.time_format = "%H.%M"
        row.fields[0].text = "03.55"
        self.assertEqual(RowType.OTHER, row.type)
        row.update_type()
        self.assertEqual(RowType.DATA, row.type)

    def test__detect_type(self) -> None:
        fields = create_fields(7, 1, 12, 7)
        row = Row.from_fields(fields)
        self.assertEqual(RowType.OTHER, row._detect_type())
        Config.time_format = "%H.%M"
        row.fields[0].text = "03.55"
        self.assertEqual(RowType.DATA, row._detect_type())
        Config.header_values = {"sunday": "6"}
        row.fields[1].text = "Sunday"
        self.assertEqual(RowType.HEADER, row._detect_type())
        Config.annot_identifier = ["annotation"]
        row.fields[1].text = "annotation"
        self.assertEqual(RowType.ANNOTATION, row._detect_type())
        Config.route_identifier = ["line"]
        row.fields[1].text = "line"
        self.assertEqual(RowType.ROUTE_INFO, row._detect_type())

    def test_split_at(self) -> None:
        table = PDFTable()
        fields = create_fields(16, 1, 12, 7)
        row = Row.from_fields(fields)
        cols = [Column.from_field(table, field) for field in fields]
        splitter = cols[3:12:4]
        rows = row.split_at(splitter)
        lens = [3, 4, 4, 5]

        self.assertEqual(len(lens), len(rows))
        self.assertListEqual(lens, list(map(len, [r.fields for r in rows])))
        for i, row in enumerate(rows[:-1]):
            for j, field in enumerate(row.fields):
                with self.subTest(i=i, j=j):
                    self.assertLess(field.bbox.x0, splitter[i].bbox.x0)


class TestColumn(P2GTestCase):
    def test_type(self) -> None:
        ...

    def test__detect_type(self) -> None:
        ...

    def test__get_repeat_intervals(self) -> None:
        ...

    def test_get_repeat_intervals(self) -> None:
        ...

    def test_merge(self) -> None:
        ...

    def test_add_field(self) -> None:
        ...

    def test_split_at(self) -> None:
        ...

    def test_from_field(self) -> None:
        ...

    def test_from_fields(self) -> None:
        ...
