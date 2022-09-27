""" Descriptors for the properties of the Config.

This is to enable a 'Config.some_property'-lookup, without the
need to hard-code each property.
"""
import datetime as dt
import logging
from pathlib import Path
from types import UnionType
from typing import Any, get_args, get_origin, Iterable, TypeVar, Union

from holidays.utils import list_supported_countries

import config.errors as err
from datastructures.gtfs_output.route import RouteType


logger = logging.getLogger(__name__)
CType = TypeVar("CType", bound="InstanceDescriptorMixin")


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

    def _raise_type_error(self, typ: type) -> None:
        logger.error(
            f"Invalid config type for {self.attr[2:]}. "
            f"Expected '{self.type}', got '{typ}' instead.")
        raise err.InvalidPropertyTypeError

    def _validate_type(self, value: Any) -> None:
        if isinstance(value, self.type):
            return
        self._raise_type_error(type(value))

    def __set__(self, obj, value: Any):
        self.validate(value)
        setattr(obj, self.attr, value)


# TODO: Needs proper errors, if oob.
class IntBoundsProperty(Property):
    def __init__(self, cls, attr, lower: int = None, upper: int = None
                 ) -> None:
        super().__init__(cls, attr, int)
        self.lower = lower
        self.upper = upper

    def validate(self, value: int) -> None:
        super().validate(value)
        self._validate_within_bounds(value)

    def _validate_within_bounds(self, value: int):
        upper_oob = self.upper and value > self.upper
        lower_oob = self.lower and value < self.lower
        if upper_oob or lower_oob:
            raise err.OutOfBoundsPropertyError


def value_to_generic(base_value: Any) -> type:
    """ Returns the generic type of a given value. """
    def get_dict_item_types() -> tuple[slice]:
        item_types: dict[type: type] = {}
        for key, value in base_value.items():
            key_type = value_to_generic(key)
            value_type = value_to_generic(value)
            item_types.setdefault(key_type, value_type)
            item_types[key_type] |= value_type
        return tuple([slice(key, value) for key, value in item_types.items()])

    def get_iter_item_types() -> Union[type]:
        item_types: set[type] = set()
        for value in base_value:
            item_types.add(value_to_generic(value))
        typ = item_types.pop()
        for item_type in item_types:
            typ |= item_type
        return typ

    base_type = type(base_value)
    # Need to check str first, because it is an Iterable but not a Generic.
    if base_type is str:
        return base_type
    if base_type is dict:
        return base_type.__class_getitem__(get_dict_item_types())
    if isinstance(base_value, Iterable):
        return base_type.__class_getitem__(get_iter_item_types())
    return base_type


class NestedTypeProperty(Property):
    def _validate_type(self, value: Any) -> None:
        try:
            self._validate_generic_type(value, self.type)
        except err.InvalidPropertyTypeError:
            self._raise_type_error(value_to_generic(value))

    def _validate_generic_type(self, value: Any, typ: type) -> None:
        if typ is None:
            return
        origin = get_origin(typ)
        if origin is None:
            if not isinstance(value, typ):
                raise err.InvalidPropertyTypeError
            return
        if origin not in [Union, UnionType]:
            self._validate_generic_type(value, origin)
        if origin is dict:
            self._validate_generic_dict(value, typ)
        elif isinstance(origin, Iterable):
            self._validate_generic_iterable(value, typ)
        else:
            self._validate_generic_type_args(value, typ)

    def _validate_generic_dict(self, value: Any, typ: type) -> None:
        args = get_args(typ)
        for key, val in value.items():
            valid = False
            for arg in args:
                try:
                    if isinstance(arg, slice):
                        self._validate_generic_type(key, arg.start)
                        self._validate_generic_type(val, arg.stop)
                        valid = True
                        continue
                    self._validate_generic_type(key, arg)
                    self._validate_generic_type(val, arg)
                    valid = True
                except err.InvalidPropertyTypeError:
                    pass
            if not valid:
                raise err.InvalidPropertyTypeError

    def _validate_generic_iterable(self, value: Any, typ: type) -> bool:
        args = get_args(typ)
        for key, val in value:
            valid = True
            for arg in args:
                if isinstance(arg, slice):
                    valid |= self._validate_generic_type(val, arg.start)
                    valid |= self._validate_generic_type(val, arg.start)
                    continue
                valid |= self._validate_generic_type(val, arg)
            if not valid:
                return False

    def _validate_generic_type_args(self, value: Any, typ: type) -> None:
        args = get_args(typ)
        if not args:
            return
        try:
            for val in value:
                valid = False
                for arg in args:
                    try:
                        self._validate_generic_type(val, arg)
                        valid = True
                        break
                    except err.InvalidPropertyTypeError:
                        pass
                if not valid:
                    raise err.InvalidPropertyTypeError
        except TypeError:
            pass


class RepeatIdentifierProperty(NestedTypeProperty):
    def __init__(self, cls: CType, attr: str) -> None:
        super().__init__(cls, attr, list[list[str]])

    def validate(self, value: Any) -> None:
        super().validate(value)
        self._validate_length(value)

    def _validate_length(self, value: list[list[str]]):
        for item in value:
            if len(item) != 2:
                logger.error(f"Every entry in '{self.attr}' needs to "
                             f"be a list of two strings. See the "
                             f"config.template.yaml for more details.")
                raise err.InvalidRepeatIdentifierError

    def __set__(self, obj, value: list):
        self.validate(value)
        return super().__set__(obj, value)


class HeaderValuesProperty(NestedTypeProperty):
    def __init__(self, cls, attr) -> None:
        super().__init__(cls, attr, dict[str: str | list[str]])

    def validate(self, value: dict):
        def _raise_invalid_header_error() -> None:
            logger.error(
                f"Invalid value for '{self.attr}': {{'{ident}': '{day}'}}")
            raise err.InvalidHeaderDaysError

        super().validate(value)
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
            raise err.InvalidHolidayCodeError
        sub = value.get("subdivision")
        if sub and sub not in supported_countries[country]:
            logger.warning(f"Invalid subdivision code '{sub}' for valid "
                           f"country '{country}' of {self.attr} entry.")
            raise err.InvalidHolidayCodeError

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


class OutputDirectoryProperty(Property):
    def __init__(self, cls, attr) -> None:
        super().__init__(cls, attr, Path)

    def __set__(self, obj, value: str | Path) -> None:
        if isinstance(value, str):
            value = value.strip()
            value = Path(value).resolve()
            if value.exists() and not value.is_dir():
                logger.error("Given output directory is not a directory.")
                raise err.InvalidOutputDirectoryError(str(value))
            if not value.exists():
                logger.info(f"Output directory '{value}' does not exist "
                            f"and will be created.")
        super().__set__(obj, value)


class DateBoundsProperty(Property):
    def __init__(self, cls, attr) -> None:
        super().__init__(cls, attr, list)

    def __set__(self, obj, value: list[str | dt.date]):
        year = dt.date.today().year
        try:
            if value == "":
                value = ["", ""]
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


class AbbrevProperty(NestedTypeProperty):
    def __init__(self, cls, attr) -> None:
        super().__init__(cls, attr, dict[str: str])

    def __set__(self, obj, value: Any):
        def _clean(string: str) -> str:
            return string.strip().lower().casefold()

        if isinstance(value, dict):
            value = {_clean(key): _clean(val) for key, val in value.items()}
            # Longer keys should come first, to prevent "hbf." to be changed
            #  to "hbahnhof", if both "hbf" and "bf" are given.
            value = dict(
                sorted(value.items(), key=lambda x: len(x[0]), reverse=True))

        super().__set__(obj, value)
