""" Functions/Classes used by many tests. """

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

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
        with open(self.path, "r") as file:
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
