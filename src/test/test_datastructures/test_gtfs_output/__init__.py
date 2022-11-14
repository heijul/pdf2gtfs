""" Helper functions used by the tests of the gtfs_output subpackage. """

from pathlib import Path
from tempfile import TemporaryDirectory

from config import Config
from test import P2GTestCase


class GTFSOutputBaseClass(P2GTestCase):
    temp_dir: TemporaryDirectory

    @classmethod
    def setUpClass(cls, name="") -> None:
        """ Create the output directory. """
        super().setUpClass(True)
        name = name if name else "test.txt"
        cls.filename = Path(cls.temp_dir.name).joinpath(name)
        Config.output_path = Path(cls.temp_dir.name)
