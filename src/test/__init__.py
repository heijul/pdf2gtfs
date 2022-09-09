from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import yaml

from config import Config


def get_test_src_dir() -> Path:
    return Config.p2g_dir.joinpath("src/test")


class Data:
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
        if not Data.instance:
            Data.instance = Data()
        return Data.instance

    def get(self, filename: str, cls: str, method: str) -> Any:
        return self.data[filename][cls][method]


def get_data_gen(file: str, cls: str) -> Callable[[str], Any]:
    def _get_data(_, method: str) -> Any:
        return Data.get_instance().get(filename, cls, method)
    filename = Path(file).name
    return _get_data
