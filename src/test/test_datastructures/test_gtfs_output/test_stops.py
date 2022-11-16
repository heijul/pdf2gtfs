from test_datastructures.test_gtfs_output import GTFSOutputBaseClass


class TestGTFSStopEntry(GTFSOutputBaseClass):
    def test_stop_lat(self) -> None:
        ...

    def test_stop_lon(self) -> None:
        ...

    def test_valid(self) -> None:
        ...

    def test_set_location(self) -> None:
        ...

    def test_get_field_value(self) -> None:
        ...

    def test_from_series(self) -> None:
        ...


class TestGTFSStops(GTFSOutputBaseClass):
    def test_add(self) -> None:
        ...

    def test_get(self) -> None:
        ...

    def test_get_by_stop_id(self) -> None:
        ...

    def test_get_existing_stops(self) -> None:
        ...
