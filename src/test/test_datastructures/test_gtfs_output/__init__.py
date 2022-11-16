""" Helper functions used by the tests of the gtfs_output subpackage. """
from pathlib import Path
from tempfile import TemporaryDirectory

from config import Config
from test import P2GTestCase


class GTFSOutputBaseClass(P2GTestCase):
    temp_dir: TemporaryDirectory
    temp_path: Path

    @classmethod
    def setUpClass(cls, name="", **kwargs) -> None:
        """ Create the output directory. """
        super().setUpClass(True)
        name = name if name else "test.txt"
        cls.filename = cls.temp_path.joinpath(name)
        Config.output_path = cls.temp_path
