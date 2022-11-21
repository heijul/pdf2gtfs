import re

import pandas as pd

from config import Config
from test import P2GTestCase
from utils import (
    get_abbreviations_regex, next_uid, normalize_series, replace_abbreviation,
    replace_abbreviations,
    UIDGenerator)


class TestUtils(P2GTestCase):
    def test_next_uid(self) -> None:
        g = UIDGenerator
        # Reset.
        g.id = None
        g.skip_ids = {"2", "3", "6"}
        self.assertEqual("0", next_uid())
        self.assertEqual("1", next_uid())
        self.assertEqual("4", next_uid())
        self.assertEqual("5", next_uid())
        self.assertEqual("7", next_uid())

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

    def test_get_abbreviations_regex(self) -> None:
        Config.name_abbreviations = {}
        regex = ""
        self.assertEqual(regex, get_abbreviations_regex())
        Config.name_abbreviations = {"str.": "strasse", "bf": "bahnhof"}
        regex += r"(\bstr\.)|(\bstr\b)|(str\.)|(\bbf\.)|(\bbf\b)"
        self.assertEqual(regex, get_abbreviations_regex())
        Config.name_abbreviations["hbf"] = "hauptbahnhof"
        regex += r"|(\bhbf\.)|(\bhbf\b)"
        self.assertEqual(regex, get_abbreviations_regex())

    def test_replace_abbreviation(self) -> None:
        Config.name_abbreviations = {
            "str.": "strasse", "bf": "bahnhof", "hbf": "hauptbahnhof"}
        name = "bf teststr. with annotations hbf"
        matches = list(re.finditer(get_abbreviations_regex(), name))
        results = ["bahnhof", "strasse", "hauptbahnhof"]
        for i, (match, result) in enumerate(zip(matches, results)):
            with self.subTest(i=i):
                self.assertEqual(result, replace_abbreviation(match))

    def test_normalize_series(self) -> None:
        series = pd.Series(["string with  multiple spaces",
                            "string with forbidden chars &/()=*'_:;",
                            "string with parentheses (with more info)",
                            "STRING with special chars straße",
                            ])
        result = ["multiple spaces string with",
                  "chars forbidden string with",
                  "parentheses string with",
                  "chars special strasse string with",
                  ]
        self.assertListEqual(result, list(normalize_series(series)))
