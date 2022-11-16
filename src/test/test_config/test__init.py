from test import P2GTestCase


class Test(P2GTestCase):
    def test__list_configs(self) -> None:
        ...

    def test__read_yaml(self) -> None:
        ...


class TestConfig(P2GTestCase):
    def test__initialize_config_properties(self) -> None:
        ...

    def test_output_dir(self) -> None:
        ...

    def test_load_default_config(self) -> None:
        ...

    def test_load_configs(self) -> None:
        ...

    def test_load_config(self) -> None:
        ...

    def test_load_args(self) -> None:
        ...

    def test__validate_no_invalid_properties(self) -> None:
        ...

    def test__validate_no_missing_properties(self) -> None:
        ...

    def test_p2g_dir(self) -> None:
        ...

    def test_config_dir(self) -> None:
        ...

    def test_default_config_path(self) -> None:
        ...

    def test__create_config_dir(self) -> None:
        ...
