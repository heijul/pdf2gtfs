from config.errors import (
    InvalidPropertyTypeError, MissingRequiredPropertyError)


class ConfigProperty:
    def __init__(self, attr, attr_type):
        self.attr = "__" + attr
        self.type = attr_type

    def __get__(self, obj, objtype=None):
        try:
            return getattr(obj, self.attr)
        except AttributeError:
            raise MissingRequiredPropertyError

    def __set__(self, obj, value):
        if not isinstance(value, self.type):
            print(f"ERROR: Invalid config type for {self.attr}. "
                  f"Expected '{self.type}', got '{type(value)}' instead.")
            raise InvalidPropertyTypeError
        setattr(obj, self.attr, value)


class PagesConfigProperty(ConfigProperty):
    def __init__(self, attr, *_):
        super().__init__(attr, list)

    def _clean_value(self, raw_value) -> list[int]:
        """ Turn the raw_value into a list of ints indicating the pages.

        Uses technically redundant assertions, but this makes
        checking for errors easier.
        """
        try:
            assert isinstance(raw_value, str)
            if raw_value == "all":
                # TODO: Create/Use Page class or use infinite sequence.
                return list(range(100))
            pages = raw_value.replace(" ", "").split(",")
            assert len(pages) >= 1
            assert all([page.isnumeric() for page in pages])
            return [int(page) for page in pages]
        except (ValueError, AssertionError):
            return raw_value

    def __set__(self, obj, value):
        if isinstance(value, str):
            value = self._clean_value(value)

        super().__set__(obj, value)
