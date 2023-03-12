from pdf2gtfs.datastructures.gtfs_output import (
    BaseContainer, BaseDataClass, str_wrap)
from test import P2GTestCase


class TestBaseDataClass(P2GTestCase):
    ...


class TestBaseContainer(P2GTestCase):
    ...


class Test(P2GTestCase):
    @classmethod
    def setUpClass(cls: P2GTestCase, **kwargs) -> None:
        super().setUpClass(True, False)

    def test_str_wrap(self) -> None:
        self.assertEqual("\"test\"", str_wrap("test"))
        self.assertEqual("\"3\"", str_wrap(3))
        c = BaseContainer("test", BaseDataClass, self.temp_path)
        self.assertEqual("\"BaseContainer: []\"", str_wrap(c))
