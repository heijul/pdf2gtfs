from pdf2gtfs.config import Config
from pdf2gtfs.datastructures.pdftable import Char
from pdf2gtfs.datastructures.pdftable.bbox import BBox
from pdf2gtfs.datastructures.pdftable.container import Column, Row
from pdf2gtfs.datastructures.pdftable.enums import FieldType
from pdf2gtfs.datastructures.pdftable.field import Field
from pdf2gtfs.datastructures.pdftable.pdftable import PDFTable
from test import P2GTestCase


class TestField(P2GTestCase):
    def setUp(self) -> None:
        self.table = PDFTable()
        self.row = Row(self.table)
        self.col = Column(self.table)
        self.bbox = BBox(10, 25, 18, 33)
        self.field = Field(self.bbox, "test")
        self.field.row = self.row
        self.field.column = self.col

    def test_type(self) -> None:
        Config.header_values = {"header test": "1, 2, 3, 4"}
        self.field.text = "Header Test"
        self.assertEqual(FieldType.HEADER, self.field.type)
        Config.repeat_identifier = [["alle", "min"]]
        self.field.text = "alle"
        self.assertEqual(FieldType.REPEAT, self.field.type)
        Config.time_format = "%H.%M"
        self.field.text = "12.03"
        self.assertEqual(FieldType.DATA, self.field.type)
        Config.arrival_identifier = ["an"]
        Config.departure_identifier = ["ab"]
        self.field.text = "an"
        self.assertEqual(FieldType.STOP_ANNOT, self.field.type)
        self.field.text = "ab"
        self.assertEqual(FieldType.STOP_ANNOT, self.field.type)
        Config.annot_identifier = ["Verkehrshinweis"]
        self.field.text = "Verkehrshinweis A"
        self.assertEqual(FieldType.ROW_ANNOT, self.field.type)
        Config.route_identifier = ["Linie"]
        self.field.text = "Linie"
        self.assertEqual(FieldType.ROUTE_INFO, self.field.type)
        self.field.text = "Anderer text"
        self.assertEqual(FieldType.OTHER, self.field.type)

        self.field.text = "stop 1"
        data_field = Field(BBox(), "14.33")
        self.row.add_field(data_field)
        field = Field(BBox(), "Long text because stops are long")
        self.col.add_field(field)
        self.assertEqual(FieldType.OTHER, self.field.type)
        self.row.update_type()
        self.col.type = self.col._detect_type()
        self.assertEqual(FieldType.STOP, self.field.type)

    def test_from_char(self) -> None:
        char = Char(110, 113, 412, 420, "t")
        field = Field.from_char(char)
        self.assertEqual("t", field.text)
        self.assertEqual(BBox(110, 412, 113, 420), field.bbox)

    def test_append_char(self) -> None:
        char = Char(110, 113, 412, 420, "t")
        field = Field.from_char(char)
        char = Char(113, 116, 412, 421, "e")
        field.append_char(char)
        self.assertEqual("te", field.text)
        self.assertEqual(BBox(110, 412, 116, 421), field.bbox)
        char = Char(116, 118.2, 411, 420, "s")
        field.append_char(char)
        self.assertEqual("tes", field.text)
        self.assertEqual(BBox(110, 411, 118.2, 421), field.bbox)
        char = Char(118.5, 120, 412, 420, "t")
        field.append_char(char)
        self.assertEqual("test", field.text)
        self.assertEqual(BBox(110, 411, 120, 421), field.bbox)

    def test_merge(self) -> None:
        field1 = Field(BBox(103, 115, 230, 239), "field1")
        field2 = Field(BBox(120, 132, 230, 239), "field2")
        field1.merge(field2)
        bbox = field1.bbox.copy()
        bbox.merge(field2.bbox)
        self.assertEqual(bbox, field1.bbox)
        self.assertEqual("field1field2", field1.text)

    def test__contains_time_data(self) -> None:
        Config.time_format = "%H.%M"
        self.assertFalse(self.field._contains_time_data())
        self.field.text = "12.30"
        self.assertTrue(self.field._contains_time_data())
        Config.time_format = "%H:%M"
        self.assertFalse(self.field._contains_time_data())
        self.field.text = "12:30"
        self.assertTrue(self.field._contains_time_data())

    def test__contains(self) -> None:
        self.field.text = "Test text contains multiple identifier"
        contained = ["test", "contains"]
        not_contained = ["identifiers", "multi"]
        for i, ident in enumerate(contained):
            self.assertTrue(self.field._contains([ident]))
        self.assertTrue(self.field._contains(contained))
        for i, ident in enumerate(not_contained):
            self.assertFalse(self.field._contains([ident]))
        self.assertFalse(self.field._contains(not_contained))
        self.assertTrue(self.field._contains(not_contained + contained))

    def test___contains__(self) -> None:
        ...

    def test__fix_name_if_split(self) -> None:
        ...
