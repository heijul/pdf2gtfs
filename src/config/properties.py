""" Descriptors for the properties of the Config.

This is to enable a 'Config.some_property'-lookup, without the
need to hard-code each property.
"""
from config.errors import (INVALID_CONFIG_EXIT_CODE,
                           InvalidPropertyTypeError,
                           MissingRequiredPropertyError)


class Property:
    def __init__(self, cls, attr, attr_type):
        self._register(cls, attr)
        self.attr = "__" + attr
        self.type = attr_type

    def _register(self, cls, attr):
        """ Ensure the instance using this property knows of its existence. """
        self.cls = cls
        self.cls.properties.append(attr)

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


class Pages:
    def __init__(self, pages_string: str = "all"):
        self.pages = set()
        self._set_value(pages_string)
        self.validate()

    def _set_value(self, pages_string):
        pages_string = pages_string.replace(" ", "")

        # TODO: Redo.
        if pages_string != "all":
            self._set_pages(pages_string)
            # pdfminer uses 0-indexed pages or None for all pages.
            self.page_numbers = [page - 1 for page in self.pages]
            return

        self.all = True
        self.page_numbers = None

    def _set_pages(self, pages_string):
        def _handle_non_numeric_pages(non_num_string):
            """ Try to expand the non_num_string to a range. """
            if "-" in non_num_string:
                try:
                    start, end = non_num_string.split("-")
                    return set(range(int(start), int(end) + 1))
                except ValueError:
                    pass
            print(f"WARNING: Skipping invalid page '{non_num_string}'. "
                  f"Reason: Non-numeric and not a proper range.")
            return set()

        for value_str in pages_string.split(","):
            if not str.isnumeric(value_str):
                self.pages.update(_handle_non_numeric_pages(value_str))
                continue
            self.pages.add(int(value_str))

        self.all = False
        self.pages = sorted(self.pages)

    def validate(self):
        if self.all:
            return

        # Page numbers are positive and start with 1.
        invalid_pages = [page for page in self.pages if page < 1]
        for page in invalid_pages:
            print(f"WARNING: Skipping invalid page '{page}'. "
                  f"Reason: Pages should be positive and begin with 1.")
            self.pages.remove(page)
        if not self.pages:
            print("ERROR: No valid pages given. Check the log for more info.")
            quit(INVALID_CONFIG_EXIT_CODE)

    def __str__(self):
        return "all" if self.all else str(list(self.pages))


class PagesProperty(Property):
    def __init__(self, cls, attr, *_):
        super().__init__(cls, attr, Pages)

    def __set__(self, obj, value):
        if isinstance(value, str):
            value = Pages(value)

        super().__set__(obj, value)


class FilenameProperty(Property):
    def __get__(self, obj, objtype=None):
        try:
            return getattr(obj, self.attr)
        except AttributeError:
            return ""
