from test import P2GTestCase


class TestBaseDataClass(P2GTestCase):
    def test_get_field_names(self) -> None:
        ...

    def test_get_field_value(self) -> None:
        ...

    def test__to_output(self) -> None:
        ...

    def test_to_output(self) -> None:
        ...


class TestBaseContainer(P2GTestCase):
    def test_read_input_file(self) -> None:
        ...

    def test_read_input_files(self) -> None:
        ...

    def test_entries_from_df(self) -> None:
        ...

    def test__add(self) -> None:
        ...

    def test__get(self) -> None:
        ...

    def test_get_header(self) -> None:
        ...

    def test_to_output(self) -> None:
        ...

    def test_write(self) -> None:
        ...

    def test__write(self) -> None:
        ...


class Test(P2GTestCase):
    def test_str_wrap(self) -> None:
        ...
