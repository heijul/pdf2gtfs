""" Helper functions used by the tests of the gtfs_output subpackage. """

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase


def _create_temp_out_dir() -> TemporaryDirectory:
    return TemporaryDirectory(prefix="pdf2gtfs_", ignore_cleanup_errors=True)


def _remove_temp_out_dir(temp_dir: TemporaryDirectory) -> None:
    temp_dir.cleanup()


class GTFSOutputBaseClass(TestCase):
    temp_dir: TemporaryDirectory

    @classmethod
    def setUpClass(cls, name="") -> None:
        """ Create the output directory. """
        cls.temp_dir = _create_temp_out_dir()
        name = name if name else "test.txt"
        cls.filename = Path(cls.temp_dir.name).joinpath(name)

    @classmethod
    def tearDownClass(cls) -> None:
        """ Remove the output directory. """
        _remove_temp_out_dir(cls.temp_dir)
