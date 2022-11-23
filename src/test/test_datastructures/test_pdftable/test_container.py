from config import Config
from datastructures.pdftable.bbox import BBox
from datastructures.pdftable.container import Column, Row
from datastructures.pdftable.enums import ColumnType, FieldType, RowType
from datastructures.pdftable.field import Field
from datastructures.pdftable.pdftable import PDFTable
from test import P2GTestCase


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

    def test_fields(self) -> None:
        fields = create_fields(7, 1, 12, 7)
        row = Row()
        row.fields = fields
        self.assertListEqual(fields, row.fields)
        for i, field in enumerate(fields):
            with self.subTest(i=i):
                self.assertEqual(row, field.row)
        self.assertEqual(fields[0].bbox.x0, row.bbox.x0)
        self.assertEqual(fields[-1].bbox.x1, row.bbox.x1)
        self.assertEqual(fields[0].bbox.y0, row.bbox.y0)
        self.assertEqual(fields[-1].bbox.y1, row.bbox.y1)

    def test_has_type(self) -> None:
        row = Row()
        self.assertFalse(row.has_type())
        row._type = RowType.OTHER
        self.assertTrue(row.has_type())
        row._type = None
        self.assertFalse(row.has_type())

    def test_add_reference_to_field(self) -> None:
        fields = create_fields(7, 1, 12, 7)
        row = Row()
        for i, field in enumerate(fields):
            with self.subTest(i=i):
                row.fields.append(field)
                self.assertNotEqual(row, field.row)
                row.add_reference_to_field(field)
                self.assertEqual(row, field.row)

    def test__add_field_at_index(self) -> None:
        fields = create_fields(7, 1, 12, 7)
        row = Row()
        for field in fields[:-1]:
            row._add_field_at_index(field, 0)
        self.assertListEqual(list(reversed(fields[:-1])), row.fields)
        row._add_field_at_index(fields[-1], 3)
        self.assertEqual(fields[-1], row.fields[3])

    def test_remove_field(self) -> None:
        fields = create_fields(7, 1, 12, 7)
        row = Row.from_fields(fields)
        count = len(row.fields)
        for i, field in enumerate(fields):
            with self.subTest(i=i):
                row.remove_field(field)
                self.assertEqual(count - 1, len(row.fields))
                with self.assertRaises(ValueError):
                    row.fields.index(field)
                count -= 1

    def test_set_bbox_from_fields(self) -> None:
        fields = create_fields(7, 1, 12, 7)
        row = Row()
        # BBox is not updated.
        row._fields = fields
        bbox = BBox()
        self.assertEqual(bbox.x0, row.bbox.x0)
        self.assertEqual(bbox.x1, row.bbox.x1)
        self.assertEqual(bbox.y0, row.bbox.y0)
        self.assertEqual(bbox.y1, row.bbox.y1)
        row.set_bbox_from_fields()
        self.assertEqual(fields[0].bbox.x0, row.bbox.x0)
        self.assertEqual(fields[-1].bbox.x1, row.bbox.x1)
        self.assertEqual(fields[0].bbox.y0, row.bbox.y0)
        self.assertEqual(fields[-1].bbox.y1, row.bbox.y1)

    def test_has_field_of_type(self) -> None:
        fields = create_fields(8, 1, 19, 33)
        row = Row()
        Config.time_format = "%H:%M"
        fields[0].text = "09:52"
        row.add_field(fields[0])
        self.assertTrue(row.has_field_of_type(FieldType.DATA))
        row.update_type()
        fields[1].text = "stop column super long"
        col = Column.from_fields([fields[1]])
        col.type = ColumnType.STOP
        row.add_field(fields[1])
        self.assertTrue(row.has_field_of_type(FieldType.STOP))
        Config.header_values = {"header": "1"}
        fields[2].text = "some text"
        row.add_field(fields[2])
        self.assertTrue(row.has_field_of_type(FieldType.OTHER))
        fields[3].text = "header"
        row.add_field(fields[3])
        self.assertTrue(row.has_field_of_type(FieldType.HEADER))
        Config.repeat_identifier = [["repeat", "min"]]
        fields[4].text = "repeat"
        row.add_field(fields[4])
        self.assertTrue(row.has_field_of_type(FieldType.REPEAT))
        Config.departure_identifier = ["ab"]
        fields[5].text = "ab"
        row.add_field(fields[5])
        self.assertTrue(row.has_field_of_type(FieldType.STOP_ANNOT))
        Config.annot_identifier = ["annotation"]
        fields[6].text = "annotation"
        row.add_field(fields[6])
        self.assertTrue(row.has_field_of_type(FieldType.ROW_ANNOT))
        Config.route_identifier = ["route"]
        fields[7].text = "route"
        row.add_field(fields[7])
        self.assertTrue(row.has_field_of_type(FieldType.ROUTE_INFO))


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
        fields[0].text = "Alle"
        fields[1].text = "4"
        fields[2].text = "min."
        self.assertEqual(["4"], col._get_repeat_intervals("alle", "min"))
        self.assertEqual(["4"], col._get_repeat_intervals("alle", "min."))
        fields[3].text = "Alle"
        fields[4].text = "5-9"
        fields[5].text = "min."
        self.assertEqual(["4", "5-9"],
                         col._get_repeat_intervals("alle", "min."))
        self.assertEqual([], col._get_repeat_intervals("allee", "min."))
        fields[1].text = "4, 6"
        self.assertEqual(["4, 6", "5-9"],
                         col._get_repeat_intervals("alle", "min."))

    def test_get_repeat_intervals(self) -> None:
        fields = create_fields(1, 8, 12, 7)
        col = Column.from_fields(fields)
        fields[0].text = "Alle"
        fields[1].text = "4"
        fields[2].text = "min."
        fields[3].text = "Every"
        fields[4].text = "5-9"
        fields[5].text = "min."
        Config.repeat_identifier = [["alle", "min"]]
        self.assertEqual(["4"], col.get_repeat_intervals())
        Config.repeat_identifier = [["alle", "min"], ["every", "min"]]
        self.assertEqual(["4", "5-9"], col.get_repeat_intervals())

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

    def test_fields(self) -> None:
        fields = create_fields(1, 16, 12, 7)
        col = Column()
        col.fields = fields
        self.assertListEqual(fields, col.fields)
        for i, field in enumerate(fields):
            with self.subTest(i=i):
                self.assertEqual(col, field.column)
        self.assertEqual(fields[0].bbox.x0, col.bbox.x0)
        self.assertEqual(fields[-1].bbox.x1, col.bbox.x1)
        self.assertEqual(fields[0].bbox.y0, col.bbox.y0)
        self.assertEqual(fields[-1].bbox.y1, col.bbox.y1)

    def test_has_type(self) -> None:
        col = Column()
        self.assertFalse(col.has_type())
        col._type = ColumnType.OTHER
        self.assertTrue(col.has_type())
        col._type = None
        self.assertFalse(col.has_type())

    def test_add_reference_to_field(self) -> None:
        fields = create_fields(1, 16, 12, 7)
        col = Column()
        for i, field in enumerate(fields):
            with self.subTest(i=i):
                col.fields.append(field)
                self.assertNotEqual(col, field.column)
                col.add_reference_to_field(field)
                self.assertEqual(col, field.column)

    def test__add_field_at_index(self) -> None:
        fields = create_fields(1, 16, 12, 7)
        col = Column()
        for field in fields[:-1]:
            col._add_field_at_index(field, 0)
        self.assertListEqual(list(reversed(fields[:-1])), col.fields)
        col._add_field_at_index(fields[-1], 3)
        self.assertEqual(fields[-1], col.fields[3])

    def test_remove_field(self) -> None:
        fields = create_fields(1, 16, 12, 7)
        col = Column.from_fields(fields)
        count = len(col.fields)
        for i, field in enumerate(fields):
            with self.subTest(i=i):
                col.remove_field(field)
                self.assertEqual(count - 1, len(col.fields))
                with self.assertRaises(ValueError):
                    col.fields.index(field)
                count -= 1

    def test_set_bbox_from_fields(self) -> None:
        fields = create_fields(1, 16, 12, 7)
        col = Column()
        # BBox is not updated.
        col._fields = fields
        bbox = BBox()
        self.assertEqual(bbox.x0, col.bbox.x0)
        self.assertEqual(bbox.x1, col.bbox.x1)
        self.assertEqual(bbox.y0, col.bbox.y0)
        self.assertEqual(bbox.y1, col.bbox.y1)
        col.set_bbox_from_fields()
        self.assertEqual(fields[0].bbox.x0, col.bbox.x0)
        self.assertEqual(fields[-1].bbox.x1, col.bbox.x1)
        self.assertEqual(fields[0].bbox.y0, col.bbox.y0)
        self.assertEqual(fields[-1].bbox.y1, col.bbox.y1)

    def test_has_field_of_type(self) -> None:
        fields = create_fields(1, 16, 12, 7)
        col = Column()

        Config.time_format = "%H:%M"
        data_field = Field(BBox(), "09:52")
        row = Row.from_fields([fields[0], data_field])
        row.update_type()
        self.assertEqual(RowType.DATA, row.type)

        fields[0].text = "stop column super long"
        col.add_field(fields[0])
        _ = col.type
        self.assertTrue(col.has_field_of_type(FieldType.STOP))

        Config.time_format = "%H:%M"
        fields[1].text = "09:52"
        col.add_field(fields[1])
        self.assertTrue(col.has_field_of_type(FieldType.DATA))
        Config.header_values = {"header": "1"}
        fields[2].text = "some text"
        col.add_field(fields[2])
        self.assertTrue(col.has_field_of_type(FieldType.OTHER))
        fields[3].text = "header"
        col.add_field(fields[3])
        self.assertTrue(col.has_field_of_type(FieldType.HEADER))
        Config.repeat_identifier = [["repeat", "min"]]
        fields[4].text = "repeat"
        col.add_field(fields[4])
        self.assertTrue(col.has_field_of_type(FieldType.REPEAT))
        Config.departure_identifier = ["ab"]
        fields[5].text = "ab"
        col.add_field(fields[5])
        self.assertTrue(col.has_field_of_type(FieldType.STOP_ANNOT))
        Config.annot_identifier = ["annotation"]
        fields[6].text = "annotation"
        col.add_field(fields[6])
        self.assertTrue(col.has_field_of_type(FieldType.ROW_ANNOT))
        Config.route_identifier = ["route"]
        fields[7].text = "route"
        col.add_field(fields[7])
        self.assertTrue(col.has_field_of_type(FieldType.ROUTE_INFO))
