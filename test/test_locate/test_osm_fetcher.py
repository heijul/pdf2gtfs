from test import P2GTestCase


class TestOSMFetcher(P2GTestCase):
    def test_cache_path(self) -> None:
        ...

    def test_cache_needs_rebuild(self) -> None:
        ...

    def test_read_cache(self) -> None:
        ...

    def test_write_cache(self) -> None:
        ...

    def test__get_raw_osm_data(self) -> None:
        ...

    def test_fetch(self) -> None:
        ...


class Test(P2GTestCase):
    def test_get_and_create_cache_dir(self) -> None:
        ...

    def test_get_osm_comments(self) -> None:
        ...

    def test_get_qlever_query(self) -> None:
        ...

    def test_raw_osm_data_to_dataframe(self) -> None:
        ...

    def test_read_data(self) -> None:
        ...
