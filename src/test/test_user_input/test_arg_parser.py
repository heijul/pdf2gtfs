from contextlib import redirect_stderr
from os import devnull

from config import Config
from config.errors import PropertyError
from test import P2GTestCase
from user_input.arg_parser import parse_args


class TestArgParser(P2GTestCase):
    @classmethod
    def setUpClass(cls: P2GTestCase, **kwargs) -> None:
        super().setUpClass(False, True)

    def test_parse_args(self) -> None:
        Config.load_default_config()
        with self.assertRaises(SystemExit):
            # Redirect stderr to /dev/null.
            with open(devnull, "w") as fnull:
                with redirect_stderr(fnull):
                    parse_args([])
        args_ns = parse_args(["test_file.pdf"])
        self.assertEqual("test_file.pdf", args_ns.filename)
        self.assertEqual(None, args_ns.time_format)
        self.assertEqual(None, args_ns.pages)
        self.assertEqual([], args_ns.config)
        self.assertEqual(None, args_ns.output_pp)
        self.assertEqual(None, args_ns.non_interactive)
        self.assertEqual(None, args_ns.display_route)
        self.assertEqual(None, args_ns.disable_location_detection)
        self.assertEqual(None, args_ns.disable_output)
        config_path = Config.default_config_path
        args = ["--time_format=%H%M",
                f"--config={config_path}",
                "--gtfs_routetype=Bus",
                f"--config={config_path}",
                "--pages=1,2,3",
                "--output_pp",
                "--non_interactive",
                "--display_route=3",
                "--disable_location_detection",
                "--disable_output",
                "test_file.pdf"]
        args_ns = parse_args(args)
        self.assertEqual("test_file.pdf", args_ns.filename)
        self.assertEqual("%H%M", args_ns.time_format)
        self.assertEqual("1,2,3", args_ns.pages)
        self.assertEqual([str(config_path), str(config_path)], args_ns.config)
        self.assertEqual(True, args_ns.output_pp)
        self.assertEqual(True, args_ns.non_interactive)
        self.assertEqual(3, args_ns.display_route)
        self.assertEqual(True, args_ns.disable_location_detection)
        self.assertEqual(True, args_ns.disable_output)

        try:
            Config.load_args(args)
        except PropertyError:
            self.fail("PropertyError raised")
