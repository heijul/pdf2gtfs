""" Descriptors for the properties of the Config.

This is to enable a 'Config.some_property'-lookup, without the
need to hard-code each property.
"""
import logging
import datetime as dt
from os import makedirs
from pathlib import Path
from typing import Any

from holidays.utils import list_supported_countries

import config.errors as err


logger = logging.getLogger(__name__)


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
            raise err.MissingRequiredPropertyError

    def validate(self, value: Any) -> None:
        self._validate_type(value)

    def _validate_type(self, value: Any) -> None:
        if isinstance(value, self.type):
            return
        logger.error(
            f"Invalid config type for {self.attr}. "
            f"Expected '{self.type}', got '{type(value)}' instead.")
        raise err.InvalidPropertyTypeError

    def __set__(self, obj, value: Any):
        self.validate(value)
        setattr(obj, self.attr, value)


class HeaderValuesProperty(Property):
    def __init__(self, cls, attr):
        super().__init__(cls, attr, dict)

    def validate(self, value: dict):
        super().validate(value)
        for ident, days in value.items():
            if not isinstance(ident, str):
                raise err.InvalidPropertyTypeError
            if not isinstance(days, str):
                raise err.InvalidPropertyTypeError
            for day in days.split(","):
                day = day.strip()
                if len(day) != 1:
                    raise err.InvalidHeaderDays
                if day == "h" or (day.isnumeric() and 0 <= int(day) <= 6):
                    continue
                raise err.InvalidHeaderDays

    def __set__(self, obj, value: dict):
        self.validate(value)
        for ident, days in value.items():
            value[ident] = list(days.split(","))
        setattr(obj, self.attr, value)


class HolidayCodeProperty(Property):
    def __init__(self, cls, attr):
        super().__init__(cls, attr, dict)

    def validate(self, value: dict[str, str]):
        super().validate(value)

        supported_countries = list_supported_countries()
        country = value.get("country")
        if country is None or country not in supported_countries:
            logger.warning(f"Invalid country code '{country}' "
                           f"for {self.attr} entry.")
            raise err.InvalidHolidayCode
        sub = value.get("subdivision")
        if sub and sub not in supported_countries[country]:
            logger.warning(f"Invalid subdivision code '{sub}' for valid "
                           f"country '{country}' of {self.attr} entry.")
            raise err.InvalidHolidayCode

    def __set__(self, obj, raw_value: dict):
        self.validate(raw_value)
        value = (raw_value.get("country"), raw_value.get("subdivision"))
        setattr(obj, self.attr, value)


class Pages:
    def __init__(self, pages_string: str = "all"):
        self.pages = set()
        self._set_value(pages_string)
        self.validate()

    def _set_value(self, pages_string):
        pages_string = pages_string.replace(" ", "")

        # pdfminer uses 0-indexed pages or None for all pages.
        if pages_string == "all":
            self.all = True
            self.page_numbers = None
            return

        self._set_pages(pages_string)
        self.page_numbers = [page - 1 for page in self.pages]

    def _set_pages(self, pages_string):
        def _handle_non_numeric_pages(non_num_string):
            """ Try to expand the non_num_string to a range. """
            if "-" in non_num_string:
                try:
                    start, end = non_num_string.split("-")
                    return set(range(int(start), int(end) + 1))
                except ValueError:
                    pass
            logger.warning(f"Skipping invalid page '{non_num_string}'. "
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
            logger.warning(f"Skipping invalid page '{page}'. Reason: "
                           f"Pages should be positive and begin with 1.")
            self.pages.remove(page)
        if not self.pages:
            logger.error("No valid pages given. Check the log for more info.")
            quit(err.INVALID_CONFIG_EXIT_CODE)

    def __str__(self):
        return "all" if self.all else str(list(self.pages))


class PagesProperty(Property):
    def __init__(self, cls, attr):
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


class RouteTypeProperty(Property):
    def __init__(self, cls, attr):
        super().__init__(cls, attr, str)

    def validate(self, value: str):
        from datastructures.gtfs_output.route import RouteType

        super().validate(value)
        if value in [typ.name for typ in RouteType]:
            return
        raise err.InvalidRouteTypeValue


class PathProperty(Property):
    def __init__(self, cls, attr):
        super().__init__(cls, attr, Path)

    def __set__(self, obj, value):
        if isinstance(value, str):
            value = Path(value).resolve()
            try:
                makedirs(value, exist_ok=True)
            except (PermissionError, NotADirectoryError, OSError) as e:
                msg = "Could not create output directory, because "
                if isinstance(e, PermissionError):
                    msg += ("you do not have the required permissions to "
                            "create the directory: '{value}'.")
                elif isinstance(e, NotADirectoryError):
                    msg += (f"a file with this name "
                            f"already exists: '{value}'.")
                else:
                    msg += f"the following error occurred: \n\t{str(e)}"
                logger.error(msg)
                raise err.InvalidPathError
            if not value.is_dir():
                raise err.InvalidPathError
        super().__set__(obj, value)


class DatesProperty(Property):
    def __init__(self, cls, attr):
        super().__init__(cls, attr, list)

    def __set__(self, obj, value: list[str | dt.date]):
        year = dt.date.today().year
        try:
            if len(value) != 2:
                raise err.InvalidDateBoundsError
            if value[0] == "":
                value[0] = f"{year}0101"
            if value[1] == "":
                value[1] = f"{year}1231"
            value[0] = dt.datetime.strptime(value[0], "%Y%m%d")
            value[1] = dt.datetime.strptime(value[1], "%Y%m%d")
        except (TypeError, KeyError, IndexError, ValueError):
            raise err.InvalidDateBoundsError

        super().__set__(obj, value)


class AbbrevProperty(Property):
    def __init__(self, cls, attr):
        super().__init__(cls, attr, dict)

    def __set__(self, obj, value: Any):
        def _clean_key(key):
            key = key.strip().lower().casefold()
            if key.endswith("."):
                return key[:-1]
            return key

        if isinstance(value, dict):
            value = {_clean_key(key): val.lower()
                     for key, val in value.items()}
            # Longer keys should come first, to prevent "hbf." to be changed
            #  to "hbahnhof", if both "hbf" and "bf" are given.
            value = dict(sorted(value.items(),
                                key=lambda item: len(item[0]),
                                reverse=True))

        super().__set__(obj, value)
