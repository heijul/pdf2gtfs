from unittest import TestCase

from finder.route_finder2 import RouteFinder
from test_finder import create_handler


class TestRouteFinder(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.handler = create_handler()

    def test_dijkstra(self) -> None:
        stop_names = [(stop.stop_id, stop.stop_name)
                      for stop in self.handler.stops.entries]
        rf = RouteFinder(self.handler, stop_names, df)
        pass
