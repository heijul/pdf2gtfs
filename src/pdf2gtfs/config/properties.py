from __future__ import annotations

import datetime as dt
import logging
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, TYPE_CHECKING
from zipfile import ZipFile

from custom_conf.errors import (
    INVALID_CONFIG_EXIT_CODE, InvalidPropertyTypeError)
from holidays.utils import list_supported_countries

from custom_conf.properties.property import CType, Property
from custom_conf.properties.bounded_property import IntBoundedProperty
from custom_conf.properties.nested_property import NestedTypeProperty

from pdf2gtfs.datastructures.gtfs_output.routes import (
    get_route_type, get_route_type_gtfs_value)
from pdf2gtfs.config.errors import (
    InvalidDateBoundsError, InvalidDirectionError, InvalidHeaderDaysError,
    InvalidHolidayCodeError, InvalidOrientationError, InvalidOutputPathError,
    InvalidRepeatIdentifierError, InvalidRouteTypeValueError,
    )


if TYPE_CHECKING:
    from pdf2gtfs.config import InstanceDescriptorMixin  # noqa: F401

logger = logging.getLogger(__name__)


class RepeatIdentifierProperty(NestedTypeProperty):
    """ Property for the repeat_identifier. """

    def __init__(self, name: str) -> None:
        super().__init__(name, list[list[str]])

    def validate(self, value: Any) -> None:
        """ Checks if the value has the correct length. """
        super().validate(value)
        self._validate_length(value)

    def _validate_length(self, value: list[list[str]]):
        for item in value:
            if len(item) != 2:
                logger.error(f"Every entry in '{self.attr}' needs to "
                             f"be a list of two strings. See the "
                             f"config.template.yaml for more details.")
                raise InvalidRepeatIdentifierError


class HeaderValuesProperty(NestedTypeProperty):
    """ Property for the header_values. """

    def __init__(self, name: str) -> None:
        super().__init__(name, dict[str: str | list[str]])

    def validate(self, value: Any):
        """ Validates the given value.

        Checks if all values of the dict are within the known header values,
        i.e. number strings 0 to 6 and character 'h'.
        """
        super().validate(value)
        self._validate_header_values(value)

    def _validate_header_values(self, value: dict[str: str | list[str]]
                                ) -> None:
        def _raise_invalid_header_error() -> None:
            logger.error(
                f"Invalid value for '{self.attr}': {{'{ident}': '{day}'}}")
            raise InvalidHeaderDaysError

        for ident, days in value.items():
            if isinstance(days, str):
                days = days.split(",")
            for day in days:
                day = day.strip()
                if len(day) != 1:
                    _raise_invalid_header_error()
                if day == "h" or (day.isnumeric() and 0 <= int(day) <= 6):
                    continue
                _raise_invalid_header_error()

    def __set__(self, obj, value: dict):
        self.validate(value)
        for ident, days in value.items():
            if isinstance(days, str):
                value[ident] = sorted([day.strip() for day in days.split(",")])
            else:
                value[ident] = sorted(days)
        setattr(obj, self.attr, value)


class HolidayCodeProperty(NestedTypeProperty):
    """ Property for the holiday code. """

    def __init__(self, name) -> None:
        super().__init__(name, dict[str: str])

    def validate(self, value: dict[str, str]):
        """ Checks if the holidays library knows the given
        country/subdivision code. """
        super().validate(value)
        self._validate_holiday_code(value)

    def _validate_holiday_code(self, value: dict[str, str]) -> None:
        country = value.get("country", "").lower()
        # Automatic adding of holiday dates is disabled.
        if not country:
            return

        supported_countries = {
            country.lower(): [sub.lower() for sub in subs]
            for country, subs in list_supported_countries().items()}
        if country not in supported_countries:
            logger.warning(f"Invalid country code '{country}' "
                           f"for {self.attr} entry.")
            raise InvalidHolidayCodeError
        sub = value.get("subdivision", "").lower()
        if not sub or sub in supported_countries[country]:
            return
        logger.warning(f"Invalid subdivision code '{sub}' for valid "
                       f"country '{country}' of {self.attr} entry.")
        raise InvalidHolidayCodeError

    def __set__(self, obj, raw_value: dict):
        self.validate(raw_value)
        value = (raw_value.get("country", "").upper(),
                 raw_value.get("subdivision", "").upper())
        if not value[0]:
            value = (None, None)

        setattr(obj, self.attr, value)


class Pages:
    """ Type of the value of the PagesProperty. """

    def __init__(self, pages_string: str = "all"):
        self.all = True
        self.pages = []
        self.set_value(pages_string)
        self.remove_invalid_pages()

    def set_value(self, pages_string: str) -> None:
        """ Set the pages to the given pages string. """
        self.all, self.pages = self._page_string_to_pages(pages_string)
        self.remove_invalid_pages()

    @property
    def page_ids(self) -> list[int] | None:
        """ Returns 0-indexed pages, or None if we have to read all pages. """
        # pdfminer uses 0-indexed pages or None for all pages.
        return None if self.all else [page - 1 for page in self.pages]

    @staticmethod
    def _page_string_to_pages(pages_string: str) -> tuple[bool, list[int]]:
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

        pages_string = pages_string.replace(" ", "")

        if pages_string == "all":
            return True, []

        pages = set()
        for value_str in pages_string.split(","):
            if not str.isnumeric(value_str):
                pages.update(_handle_non_numeric_pages(value_str))
                continue
            pages.add(int(value_str))

        return False, sorted(pages)

    def page_num(self, page_id: int) -> int:
        """ Returns the pagenumber (i.e. the page of the pdf) at page_id. """
        return page_id if self.all else self.pages[page_id - 1]

    def remove_invalid_pages(self) -> None:
        """ Checks that the pages start at 1 (pdf page). """
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
            quit(INVALID_CONFIG_EXIT_CODE)

    def to_string(self) -> str:
        def page_range_to_string() -> list[str]:
            """ Turns the page_range into either a range string (e.g. 1-5) or
            a list of strings (e.g. 1, 2). """
            if page_range[1] - page_range[0] >= 2:
                return [f"{page_range[0]}-{page_range[1]}"]
            return [str(i) for i in range(page_range[0], page_range[1] + 1)]

        if self.all:
            return ""
        pages = []
        page_range = [None, None]
        for page in self.pages:
            if page_range[0] is None:
                page_range = [page, page]
                continue
            if page == page_range[1] + 1:
                page_range[1] = page
                continue
            pages += page_range_to_string()
            page_range = [page, page]
        if page_range != [None, None]:
            pages += page_range_to_string()
        return ", ".join(map(str, pages))

    def __str__(self) -> str:
        return "all" if self.all else str(list(self.pages))


class PagesProperty(Property):
    """ Property used to define the pages, that should be read. """

    def __init__(self, name) -> None:
        super().__init__(name, Pages)

    def __set__(self, obj: CType, value: str | Pages) -> None:
        if isinstance(value, str):
            pages = Pages()
            pages.set_value(value)
            value = pages

        super().__set__(obj, value)


class FilenameProperty(Property):
    """ Property defining a filename. """

    def __get__(self, obj, objtype=None) -> str:
        try:
            return getattr(obj, self.attr)
        except AttributeError:
            return ""


class RouteTypeProperty(Property):
    """ Property for the gtfs_routetype. """

    def __init__(self, name) -> None:
        super().__init__(name, str)

    def validate(self, value: str) -> None:
        """ Checks if there are any obvious errors with the value. """
        super().validate(value)
        self._validate_route_type(value)

    @staticmethod
    def _validate_route_type(value: str) -> None:
        route_type = get_route_type(value)
        if route_type is None:
            raise InvalidRouteTypeValueError

    def __set__(self, obj, value: str) -> None:
        self.validate(value)
        route_type = get_route_type(value)
        return super().__set__(obj, route_type.name)


class OutputPathProperty(Property):
    """ Property for the output directory. """

    def __init__(self, name) -> None:
        super().__init__(name, Path)

    @staticmethod
    def _validate_path(path: Path) -> None:
        is_zip_name = path.name.endswith(".zip")

        if path.exists() and path.is_file() and not is_zip_name:
            logger.error("The given output path already exists, "
                         "but is not a .zip file.")
            raise InvalidOutputPathError

        if is_zip_name:
            dir_path = path.parent
            name_msg = f"set to '{path.name}'"
        else:
            dir_path = path
            name_msg = ("chosen based on the current date, time and "
                        "the name of the input file")
        logger.info(f"GTFS-feed will be exported to '{dir_path}'. The name "
                    f"of the feed will be {name_msg}.")
        if not dir_path.exists():
            logger.info(f"Output directory '{dir_path}' does not exist "
                        f"and will be created.")

    def __set__(self, obj, value: str | Path) -> None:
        if isinstance(value, Path):
            super().__set__(obj, value)
            return

        path = Path(value.strip()).resolve()
        super().__set__(obj, path)


class DateBoundsProperty(Property):
    """ Property for the start-/end dates of the gtfs calendar. """

    def __init__(self, name) -> None:
        super().__init__(name, list)

    @staticmethod
    def clean_value(value: str | list[str | dt.date]
                    ) -> list[dt.datetime, dt.datetime]:
        """ Return the value in the valid format or raise an error. """
        year = dt.date.today().year
        try:
            if value == "":
                value = ["", ""]
            if len(value) != 2:
                raise InvalidDateBoundsError
            if value[0] == "":
                value[0] = f"{year}0101"
            if value[1] == "":
                value[1] = f"{year}1231"
            return [dt.datetime.strptime(value[0], "%Y%m%d"),
                    dt.datetime.strptime(value[1], "%Y%m%d")]
        except (TypeError, KeyError, IndexError, ValueError):
            raise InvalidDateBoundsError

    def __set__(self, obj, value: list[str | dt.date]):
        super().__set__(obj, self.clean_value(value))


class DirectionProperty(Property):
    def __init__(self, name: str) -> None:
        super().__init__(name, str)

    def validate(self, value: str) -> None:
        super().validate(value)
        value = "".join(set(value.upper()))
        for char in value:
            if char not in "NWSE":
                raise InvalidDirectionError(prop=self, direction=char)


class SplitOrientationsProperty(Property):
    def __init__(self, name: str) -> None:
        super().__init__(name, str)

    def validate(self, value: str) -> None:
        super().validate(value)
        value = "".join(set(value.upper()))
        for char in value:
            if char not in "VH":
                raise InvalidOrientationError(prop=self, orientation=char)


class AbbrevProperty(NestedTypeProperty):
    """ Property used by the abbreviations. """

    def __init__(self, name) -> None:
        super().__init__(name, dict[str: str])

    @staticmethod
    def clean_value(value: dict[str: str]) -> dict[str: str]:
        """ Sort the abbreviations by length and normalize them. """

        def _clean(string: str) -> str:
            return string.strip().lower().casefold()

        value = {_clean(key): _clean(val) for key, val in value.items()}
        # Longer keys should come first, to prevent "hbf." to be changed
        #  to "hbahnhof", if both "hbf" and "bf" are given.
        return dict(
            sorted(value.items(), key=lambda x: len(x[0]), reverse=True))

    def __set__(self, obj, value: Any):
        super().__set__(obj, self.clean_value(value))


class AverageSpeedProperty(IntBoundedProperty):
    """ Property for the average_speed. If set to 0, return a sane default. """

    def __init__(self, name) -> None:
        super().__init__(name, 0, 200)

    def __get__(self, obj: CType, objtype=None) -> Any:
        # Override get instead of set, to autodetect the speed. Otherwise,
        #  setting the routetype would not necessarily update the speed.
        value = super().__get__(obj, objtype)
        if value != 0:
            return value
        routetype = get_route_type(obj.gtfs_routetype)

        defaults = {0: 25, 1: 35, 2: 50, 3: 15, 4: 20,
                    5: 10, 6: 10, 7: 10, 11: 15, 12: 35}
        return defaults[get_route_type_gtfs_value(routetype)]


class InputProperty(NestedTypeProperty):
    """ Property for providing GTFS-feeds or files. """

    def __init__(self, name: str) -> None:
        self.temp_dir = None
        super().__init__(name, dict[str: list[Path]])

    def __del__(self) -> None:
        if self.temp_dir is None:
            return
        self.temp_dir.cleanup()

    def __set__(self, obj, value: Any) -> None:
        if not isinstance(value, list):
            raise InvalidPropertyTypeError

        paths = []
        for path_str in value:
            paths += self.get_paths_for_input_path(Path(path_str).resolve())
        paths = set(paths)

        path_dict = {}
        for path in paths:
            path_dict.setdefault(path.name, []).append(path)
        self.validate(path_dict)
        super().__set__(obj, path_dict)

    def get_paths_for_input_path(self, input_path: Path) -> list[Path]:
        """ Get all file paths for the given path. """
        if not input_path.exists():
            logger.warning(f"The given input path '{input_path}' "
                           f"does not exist.")
            return []
        # Directory.        # Directory.
        if input_path.is_dir():
            return list(input_path.glob("*.txt"))
        # GTFS feed.
        if input_path.name.endswith(".zip"):
            logger.info("Input file is a zip archive. Extracting...")
            self.temp_dir = TemporaryDirectory()
            with ZipFile(input_path, "r") as zip_file:
                zip_file.extractall(self.temp_dir.name)
            logger.info("Done.")
            return list(Path(self.temp_dir.name).glob("*.txt"))
        # Single GTFS file.
        if input_path.name.endswith(".txt"):
            return [input_path]

        logger.warning(f"The given input path '{input_path}' is not a valid "
                       f"input path. See the template config for more info.")
        return []
