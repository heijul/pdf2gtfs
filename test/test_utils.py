from unittest import TestCase

from utils import get_edit_distance


class TestUtils(TestCase):
    def test_get_edit_distance(self):
        self.assertEqual(3, get_edit_distance("sitting", "kitten"))
        self.assertEqual(3, get_edit_distance("kitten", "sitting"))
        self.assertEqual(3, get_edit_distance("sunday", "saturday"))
        self.assertEqual(3, get_edit_distance("saturday", "sunday"))
