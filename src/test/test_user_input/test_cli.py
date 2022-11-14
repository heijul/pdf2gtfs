import platform
from pathlib import Path
from unittest import mock

from config import Config
from test import P2GTestCase
from user_input.cli import create_output_directory


def get_path_with_insufficient_permissions() -> str:
    """ Returns a platform-dependent path, where the user (hopefully) has
    not enough permissions for.
    """
    if platform.system().lower() == "windows":
        return "C:/Windows/pdf2gtfs/"
    return "/pdf2gtfs/"


class TestCLI(P2GTestCase):
    @classmethod
    def setUpClass(cls: P2GTestCase, create_temp_dir: bool = True) -> None:
        super().setUpClass(create_temp_dir)

    @mock.patch("user_input.cli.input", create=True)
    def test_create_output_directory(self, mock_input: mock.Mock) -> None:
        # Enable interactive mode.
        Config.non_interactive = False

        # Test failing creation. (Permission error)
        mock_input.side_effect = ["", "", "", "", "q"]
        path = get_path_with_insufficient_permissions()
        Config.output_path = path
        self.assertFalse(Path(path).exists())
        result = create_output_directory()
        self.assertFalse(result)
        self.assertEqual(5, mock_input.call_count)
        self.assertFalse(Path(path).exists())
        mock_input.reset_mock()

        # Test valid creation.
        path = Path(self.temp_dir.name).joinpath("output_dir_test")
        Config.output_path = path
        self.assertFalse(Path(path).exists())
        result = create_output_directory()
        self.assertTrue(result)
        self.assertTrue(Path(path).exists())
        mock_input.reset_mock()

    def test_create_output_directory__non_interactive(self) -> None:
        # Disable interactive mode.
        Config.non_interactive = True

        # Test failing creation. (Permission error)
        path = get_path_with_insufficient_permissions()
        Config.output_path = path
        self.assertFalse(Path(path).exists())
        result = create_output_directory()
        self.assertFalse(result)
        self.assertFalse(Path(path).exists())

        # Test valid creation.
        path = Path(self.temp_dir.name).joinpath(
            "output_dir_test__non_interactive")
        Config.output_path = path
        self.assertFalse(Path(path).exists())
        result = create_output_directory()
        self.assertTrue(result)
        self.assertTrue(Path(path).exists())
