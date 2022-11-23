from config import Config
from datastructures.pdftable.bbox import BBox
from datastructures.pdftable.container import Column, Row
from datastructures.pdftable.enums import ColumnType, RowType
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
    def setUp(self) -> None:
        self.table = PDFTable()

    def test_type(self) -> None:
        fields = create_fields(1, 8, 12, 7)
        col = Column.from_fields(fields)
        self.assertFalse(col.has_type())
        self.assertEqual(ColumnType.OTHER, col.type)
        Config.time_format = "%H.%M"
        col.fields[0].text = "03.55"
        self.assertEqual(ColumnType.OTHER, col.type)
        col.type = col._detect_type()
        self.assertEqual(ColumnType.DATA, col.type)
        self.assertTrue(col.has_type())
        col.type = ColumnType.REPEAT
        self.assertEqual(ColumnType.REPEAT, col.type)

    def test__detect_type(self) -> None:
        fields = create_fields(2, 8, 12, 7)
        col1 = Column.from_fields(
            [f for i, f in enumerate(fields) if i % 2 == 2])
        col2 = Column.from_fields(
            [f for i, f in enumerate(fields) if i % 2 == 1])
        col1.table = self.table
        col2.table = self.table
        self.table.columns.add(col1)
        self.table.columns.add(col2)
        self.assertEqual(col1, self.table.columns.prev(col2))

        self.assertEqual(ColumnType.OTHER, col2._detect_type())
        Config.time_format = "%H.%M"
        col2.fields[0].text = "03.55"
        Config.time_format = "%H.%M"
        self.assertEqual(ColumnType.DATA, col2._detect_type())
        Config.repeat_identifier = [["alle", "min."]]
        col2.fields[0].text = "alle"
        col2.fields[1].text = "10"
        col2.fields[2].text = "min."
        self.assertEqual(ColumnType.REPEAT, col2._detect_type())

        col1.type = ColumnType.STOP
        Config.arrival_identifier = ["ab"]
        col2.fields[0].text = "ab"
        self.assertEqual(ColumnType.STOP_ANNOTATION, col2._detect_type())

    def test__get_repeat_intervals(self) -> None:
        fields = create_fields(1, 8, 12, 7)
        col = Column.from_fields(fields)
        ...

    def test_get_repeat_intervals(self) -> None:
        fields = create_fields(1, 8, 12, 7)
        col = Column.from_fields(fields)
        ...

    def test_merge(self) -> None:
        fields1 = create_fields(1, 8, 12, 7)
        col1 = Column.from_fields(fields1)
        fields2 = create_fields(1, 8, 12, 7)
        cols = [Column.from_field(self.table, f) for f in fields2]
        col2 = cols.pop(0)
        for col in cols:
            col2.merge(col)
        self.assertEqual(col1.bbox.x0, col2.bbox.x0)
        self.assertEqual(col1.bbox.x1, col2.bbox.x1)
        self.assertEqual(col1.bbox.y0, col2.bbox.y0)
        self.assertEqual(col1.bbox.y1, col2.bbox.y1)

    def test_add_field(self) -> None:
        fields1 = create_fields(1, 8, 12, 7)
        fields2 = create_fields(1, 8, 12, 7)
        col1 = Column.from_fields(fields1[:-1])
        col2 = Column.from_fields(fields2)
        col1.add_field(fields1[-1])
        self.assertEqual(col1.bbox.x0, col2.bbox.x0)
        self.assertEqual(col1.bbox.x1, col2.bbox.x1)
        self.assertEqual(col1.bbox.y0, col2.bbox.y0)
        self.assertEqual(col1.bbox.y1, col2.bbox.y1)

    def test_split_at(self) -> None:
        fields = create_fields(1, 16, 12, 7)
        col = Column.from_fields(fields)
        splitter = []
        for i in range(3, 14, 5):
            splitter.append(Row.from_fields([fields[i]]))
        cols = col.split_at(splitter)

        lens = [3, 5, 5, 3]
        self.assertEqual(len(lens), len(cols))
        self.assertListEqual(lens, list(map(len, [c.fields for c in cols])))
        for i, row in enumerate(cols[:-1]):
            for j, field in enumerate(col.fields):
                with self.subTest(i=i, j=j):
                    self.assertLess(field.bbox.x0, splitter[i].bbox.x0)

    def test_from_field(self) -> None:
        field = create_fields(1, 1, 12, 7)[0]
        col = Column.from_field(self.table, field)
        self.assertEqual(field.bbox.x0, col.bbox.x0)
        self.assertEqual(field.bbox.x1, col.bbox.x1)
        self.assertEqual(field.bbox.y0, col.bbox.y0)
        self.assertEqual(field.bbox.y1, col.bbox.y1)
        self.assertEqual(col, field.column)

    def test_from_fields(self) -> None:
        fields = create_fields(1, 8, 12, 7)
        col = Column.from_fields(fields)
        self.assertEqual(fields, col.fields)
        bbox = BBox(fields[0].bbox.x0, fields[0].bbox.y0,
                    fields[-1].bbox.x1, fields[-1].bbox.y1)
        self.assertEqual(bbox, col.bbox)
