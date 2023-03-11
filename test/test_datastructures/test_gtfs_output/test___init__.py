from pdf2gtfs.datastructures.gtfs_output import (
    BaseContainer, BaseDataClass, str_wrap)
from test import P2GTestCase


class TestBaseDataClass(P2GTestCase):
    # TODO: Check how we can test this. BaseDataClass has no fields...
    #  Maybe test it in the subclasses, instead?
    ...


class TestBaseContainer(P2GTestCase):
    # TODO: Check how we can test this. BaseContainer needs an entry_type...
    #  Maybe test it in the subclasses, instead?
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
