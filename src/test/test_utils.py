from config import Config
from utils import replace_abbreviations

from test import P2GTestCase


class TestUtils(P2GTestCase):
    def test_replace_abbreviations__no_dot(self) -> None:
        Config.name_abbreviations = {"str": "strasse"}
        names = {"hauptstr.": "hauptstr.",
                 "hauptstr": "hauptstr",
                 "haupt str.": "haupt strasse",
                 "haupt str": "haupt strasse",
                 "strasse": "strasse",
                 "bf str": "bf strasse",
                 "hauptstrberg": "hauptstrberg",
                 }
        for short_name, full_name in names.items():
            self.assertEqual(full_name, replace_abbreviations(short_name))

    def test_replace_abbreviations__with_dot(self) -> None:
        Config.name_abbreviations = {"str.": "strasse"}
        names = {"hauptstr.": "hauptstrasse",
                 "hauptstr": "hauptstr",
                 "haupt str.": "haupt strasse",
                 "haupt str": "haupt strasse",
                 "strasse": "strasse",
                 "bf str": "bf strasse",
                 "hauptstrberg": "hauptstrberg",
                 }
        for short_name, full_name in names.items():
            self.assertEqual(full_name, replace_abbreviations(short_name))

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
                 "hbf": "hauptbahnhof",
                 "hauptstrberg": "hauptstrberg",
                 }
        for short_name, full_name in names.items():
            self.assertEqual(full_name, replace_abbreviations(short_name))
