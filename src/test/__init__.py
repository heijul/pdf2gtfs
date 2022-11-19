""" Functions/Classes used by many tests. """

from __future__ import annotations

import logging
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Callable
from unittest import TestCase

import yaml

from config import Config


def get_test_src_dir() -> Path:
    """ Returns the directory, where the tests are located. """
    return Config.p2g_dir.joinpath("src/test")


class Data:
    """ Provides methods to get test data from the test/data dir. """
    instance = None

    def __init__(self) -> None:
        if Data.instance:
            raise Exception("Singleton.")
        self.__initialize()

    def __initialize(self) -> None:
        self.path = get_test_src_dir().joinpath("data/data.yaml")
        with open(self.path, "r", encoding="utf-8") as file:
            self.data = yaml.load(file, Loader=yaml.BaseLoader)

    @staticmethod
    def get_instance() -> Data:
        """ Return the single Data instance, creating it if necessary. """
        if not Data.instance:
            Data.instance = Data()
        return Data.instance

    def get(self, filename: str, cls: str, method: str) -> Any:
        """ Return the data for a given test-file/-class/-method. """
        return self.data[filename][cls][method]


def get_data_gen(file: str, cls: str) -> Callable[[str], Any]:
    """ Convenience function, to make multiple calls
    from the same file/class easier. """

    def _get_data(_, method: str) -> Any:
        return Data.get_instance().get(filename, cls, method)

    filename = Path(file).name
    return _get_data


class P2GTestCase(TestCase):
    """ Base class for test cases (super().setUp() has to be called by subs).

    Ensures that we always use the default config, even if one test changed it.
    """

    temp_dir: TemporaryDirectory | None
    temp_path: Path | None

    def __init__(self, methodName: str = "runTest") -> None:
        super().__init__(methodName)

    @classmethod
    def setUpClass(cls: P2GTestCase,
                   create_temp_dir: bool = False,
                   disable_logging: bool = False) -> None:
        super().setUpClass()
        Config.filename = str(get_test_src_dir().joinpath("data/vag_1.pdf"))
        cls.temp_dir = None
        cls.temp_path = None
        if create_temp_dir:
            # TODO: Create a single pdf2gtfs temp dir, where all
            #  test temp_dirs are located.
            cls.temp_dir = TemporaryDirectory(prefix="pdf2gtfs_test_")
            cls.temp_path = Path(cls.temp_dir.name)
        if disable_logging:
            logging.disable(logging.CRITICAL)

    @classmethod
    def tearDownClass(cls: P2GTestCase) -> None:
        super().tearDownClass()
        if cls.temp_dir is not None:
            cls.temp_dir.cleanup()
        # No need to check if disabled.
        logging.disable(logging.NOTSET)

    def setUp(self) -> None:
        super().setUp()
        # Reset the config. Easier/Less error-prone than cleaning up properly.
        Config.load_default_config()
        Config.output_pp = False
