""" Descriptors for the properties of the Config.

This is to enable a 'Config.some_property'-lookup, without the
need to hard-code each property.
"""
import datetime as dt
import logging
from pathlib import Path
from typing import Any, TypeVar

from holidays.utils import list_supported_countries

import config.errors as err
from config import InstanceDescriptorMixin
from datastructures.gtfs_output.route import RouteType


logger = logging.getLogger(__name__)
CType = TypeVar("CType", bound=InstanceDescriptorMixin)


class Property:
    def __init__(self, cls: CType, attr: str, attr_type: type) -> None:
        self._register(cls, attr)
        self.attr = "__" + attr
        self.type = attr_type

    def _register(self, cls: CType, attr: str) -> None:
        """ Ensure the instance using this property knows of its existence. """
        self.cls = cls
        self.cls.properties.append(attr)

    def __get__(self, obj: CType, objtype=None) -> Any:
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
    def __init__(self, cls, attr) -> None:
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
    def __init__(self, cls, attr) -> None:
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
        self.pages = []
        self._set_value(pages_string)
        self.validate()

    def _set_value(self, pages_string: str) -> None:
        pages_string = pages_string.replace(" ", "")

        if pages_string == "all":
            self.all = True
            return

        self._set_pages(pages_string)

    @property
    def page_ids(self) -> list[int] | None:
        # pdfminer uses 0-indexed pages or None for all pages.
        return None if self.all else [page - 1 for page in self.pages]

    def _set_pages(self, pages_string: str) -> None:
        def _handle_non_numeric_pages(non_num_string: str) -> set[int]:
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

        pages = set()
        for value_str in pages_string.split(","):
            if not str.isnumeric(value_str):
                pages.update(_handle_non_numeric_pages(value_str))
                continue
            pages.add(int(value_str))

        self.all = False
        self.pages = sorted(pages)

    def page_num(self, page_id: int) -> int:
        return page_id if self.all else self.pages[page_id - 1]

    def validate(self) -> None:
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

    def __str__(self) -> str:
        return "all" if self.all else str(list(self.pages))


class PagesProperty(Property):
    def __init__(self, cls, attr) -> None:
        super().__init__(cls, attr, Pages)

    def __set__(self, obj: CType, value: str | Pages) -> None:
        if isinstance(value, str):
            value = Pages(value)

        super().__set__(obj, value)


class FilenameProperty(Property):
    def __get__(self, obj, objtype=None) -> str:
        try:
            return getattr(obj, self.attr)
        except AttributeError:
            return ""


class RouteTypeProperty(Property):
    def __init__(self, cls, attr) -> None:
        super().__init__(cls, attr, RouteType)

    def __set__(self, obj, value: str | int) -> None:
        value = value.strip()
        value = int(value) if value.isnumeric() else value
        if isinstance(value, str):
            value = RouteType[value]
        elif isinstance(value, int):
            value = RouteType(value)
        return super().__set__(obj, value)


class PathProperty(Property):
    def __init__(self, cls, attr) -> None:
        super().__init__(cls, attr, Path)

    def __set__(self, obj, value: str | Path) -> None:
        if isinstance(value, str):
            value = Path(value).resolve()
            if value.exists() and not value.is_dir():
                logger.error("Output directory is not a directory.")
                raise err.InvalidOutputDirectory
            if not value.exists():
                logger.info(f"Output directory '{value}' does not exist "
                            f"and will be created.")
        super().__set__(obj, value)


class DatesProperty(Property):
    def __init__(self, cls, attr) -> None:
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
    def __init__(self, cls, attr) -> None:
        super().__init__(cls, attr, dict)

    def __set__(self, obj, value: Any):
        def _clean_key(key: str) -> str:
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
