from unittest import TestCase

from config import Config
from utils import get_edit_distance, replace_abbreviations


class TestUtils(TestCase):
    def test_get_edit_distance(self) -> None:
        self.assertEqual(3, get_edit_distance("sitting", "kitten"))
        self.assertEqual(3, get_edit_distance("kitten", "sitting"))
        self.assertEqual(3, get_edit_distance("sunday", "saturday"))
        self.assertEqual(3, get_edit_distance("saturday", "sunday"))

    def test_replace_abbreviations(self) -> None:
        Config.name_abbreviations = {
            "str.": "strasse", "bf": "bahnhof", "hbf": "hauptbahnhof"}
        names = {"hauptstr.": "hauptstrasse",
                 "hauptstr": "hauptstr",
                 "haupt str.": "haupt strasse",
                 "haupt str": "haupt strasse",
                 "strasse": "strasse",
                 "frankfurt bf": "frankfurt bahnhof",
                 "frankfurt hbf.": "frankfurt hauptbahnhof",
                 "bf str": "bahnhof strasse",
                 "hauptstrberg": "hauptstrberg",
                 }
        for short_name, full_name in names.items():
            self.assertEqual(full_name, replace_abbreviations(short_name))
