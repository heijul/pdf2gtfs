import logging
from pathlib import Path
from typing import Any

from yaml import safe_load, YAMLError
from yaml.scanner import ScannerError

import config.errors as err
from config.properties import (Property, PagesProperty, FilenameProperty,
                               HolidayCodeProperty, HeaderValuesProperty, RouteTypeProperty)


logger = logging.getLogger(__name__)


class InstanceDescriptorMixin:
    """ Enable descriptors on an instance instead of a class.
    See https://blog.brianbeck.com/post/74086029/instance-descriptors
    """

    def __getattribute__(self, name):
        value = object.__getattribute__(self, name)
        if hasattr(value, '__get__'):
            value = value.__get__(self, self.__class__)
        return value

    def __setattr__(self, name, value):
        try:
            obj = object.__getattribute__(self, name)
        except AttributeError:
            pass
        else:
            if hasattr(obj, '__set__'):
                return obj.__set__(self, value)
        return object.__setattr__(self, name, value)


class _Config(InstanceDescriptorMixin):
    def __init__(self):
        self._initialize_config_properties()
        # Always load default config first, before loading any custom config
        # or program parameters.
        default_config_loaded = self.load_config(None)
        if not default_config_loaded:
            logger.error("Default config could not be loaded. Exiting...")
            quit(err.INVALID_CONFIG_EXIT_CODE)

    def _initialize_config_properties(self):
        self.properties = []
        self.time_format = Property(self, "time_format", str)
        self.header_values = HeaderValuesProperty(self, "header_values")
        self.holiday_code = HolidayCodeProperty(self, "holiday_code")
        self.repeat_identifier = Property(self, "repeat_identifier", list)
        self.repeat_strategy = Property(self, "repeat_strategy", str)
        self.min_table_rows = Property(self, "min_table_rows", int)
        self.pages = PagesProperty(self, "pages")
        self.max_row_distance = Property(self, "max_row_distance", int)
        self.min_row_count = Property(self, "min_row_count", int)
        self.filename = FilenameProperty(self, "filename", str)
        self.annot_identifier = Property(self, "annot_identifier", list)
        self.route_identifier = Property(self, "route_identifier", list)
        self.gtfs_routetype = RouteTypeProperty(self, "gtfs_routetype", str)

    def load_config(self, path: Path | None = None) -> bool:
        """ Load the given config. If no config is given, load the default one.

        :param path: Path to config file, or None to load the default config.
        :return: True, if loading was a success, False if any errors occurred.
        """
        if not path:
            path = self.default_config_path
        if not path.exists():
            logger.warning(f"File does not exist, skipping: {path}")
            return False

        data, valid = _read_yaml(path)

        # TODO: Catch other PropertyExceptions as well.
        for key, value in data.items():
            # Even if an item is invalid, continue reading to find all errors.
            try:
                if key not in self.properties:
                    logger.error(f"Invalid config key: {key}")
                    raise err.InvalidPropertyTypeError
                setattr(self, key, value)
            except err.InvalidPropertyTypeError:
                valid = False

        valid &= self._validate_no_missing_properties()

        if not valid:
            logger.error("Tried to load invalid configuration file "
                         f"'{path}'. Exiting...")
            quit(err.INVALID_CONFIG_EXIT_CODE)

        return True

    def load_args(self, args: dict[str, Any]):
        for path in args.pop("config", []):
            self.load_config(Path(path).resolve())

        for name, value in args.items():
            if value is None:
                continue
            if name in self.properties:
                setattr(self, name, value)

    def _validate_no_missing_properties(self):
        missing_keys = []
        for key in self.properties:
            try:
                getattr(self, key)
            except err.MissingRequiredPropertyError:
                missing_keys.append(key)

        if missing_keys:
            logger.warning(
                "The following values are required, but are missing in "
                "the configuration: ['{}']. This usually only happens, "
                "if the default configuration was changed, instead of "
                "creating a custom one.".format("', '".join(missing_keys)))
            return False
        return True

    @property
    def base_path(self) -> Path:
        return Path(__file__).parents[2]

    @property
    def default_config_path(self):
        return self.base_path.joinpath("config.template.yaml")

    def __str__(self):
        string_like = (str, Path)

        def get_property_string(_name, _value):
            wrapper = "'" if isinstance(_value, string_like) else ""
            return f"\t{_name:{max_name_len}}: {wrapper}{_value}{wrapper}"

        base_string = "\nCurrent configuration: [\n{}\n]"

        property_names = self.properties + ["base_path", "default_config_path"]
        max_name_len = max(len(name) for name in property_names)

        # This can only fail if some properties are missing. However, in
        # that case we have already quit.
        prop_strings = [get_property_string(name, getattr(self, name))
                        for name in property_names]

        return base_string.format("\n".join(prop_strings))


def _read_yaml(path: Path) -> tuple[dict[str, Any], bool]:
    try:
        with open(path) as config_file:
            return safe_load(config_file), True
    except (ScannerError, YAMLError) as error:
        if isinstance(error, ScannerError):
            # Indent error message.
            message = "\n\t".join(str(error).split("\n"))
        else:
            message = str(error)
        logger.error(f"Could not read configuration:\n\t{message}")
    return {}, False


Config = _Config()
