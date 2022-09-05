import logging
import os.path
import platform
import shutil
from pathlib import Path
from typing import Any

from yaml import safe_load, YAMLError
from yaml.scanner import ScannerError

import config.errors as err
from config.properties import (
    AbbrevProperty, DateBoundsProperty, FilenameProperty,
    HeaderValuesProperty, HolidayCodeProperty, IntBoundsProperty,
    OutputDirectoryProperty, PagesProperty, Property, RouteTypeProperty)


logger = logging.getLogger(__name__)


class InstanceDescriptorMixin:
    """ Enable descriptors on an instance instead of a class.
    See https://blog.brianbeck.com/post/74086029/instance-descriptors
    """

    def __getattribute__(self, name: str) -> Any:
        value = object.__getattribute__(self, name)
        if hasattr(value, '__get__'):
            value = value.__get__(self, self.__class__)
        return value

    def __setattr__(self, name: str, value: Any) -> None:
        try:
            obj = object.__getattribute__(self, name)
        except AttributeError:
            pass
        else:
            if hasattr(obj, '__set__'):
                return obj.__set__(self, value)
        return object.__setattr__(self, name, value)


def _list_configs(directory: Path) -> list[Path]:
    return list(directory.glob("*.yaml")) + list(directory.glob("*.yml"))


class _Config(InstanceDescriptorMixin):
    def __init__(self) -> None:
        self._create_default_config()
        self._initialize_config_properties()
        self.load_configs()

    def _initialize_config_properties(self) -> None:
        self.properties = []
        self.time_format = Property(self, "time_format", str)
        self.header_values = HeaderValuesProperty(self, "header_values")
        self.holiday_code = HolidayCodeProperty(self, "holiday_code")
        self.repeat_identifier = Property(self, "repeat_identifier", list)
        self.repeat_strategy = Property(self, "repeat_strategy", str)
        self.pages = PagesProperty(self, "pages")
        self.max_row_distance = IntBoundsProperty(self, "max_row_distance", 0)
        self.min_row_count = IntBoundsProperty(self, "min_row_count", 0)
        self.filename = FilenameProperty(self, "filename", str)
        self.annot_identifier = Property(self, "annot_identifier", list)
        self.route_identifier = Property(self, "route_identifier", list)
        self.gtfs_routetype = RouteTypeProperty(self, "gtfs_routetype")
        self.allowed_stop_chars = Property(self, "allowed_stop_chars", list)
        self.max_stop_distance = IntBoundsProperty(
            self, "max_stop_distance", 0)
        self.output_dir = OutputDirectoryProperty(self, "output_dir")
        self.preprocess = Property(self, "preprocess", bool)
        self.output_pp = Property(self, "output_pp", bool)
        self.always_overwrite = Property(self, "always_overwrite", bool)
        self.non_interactive = Property(self, "non_interactive", bool)
        self.gtfs_date_bounds = DateBoundsProperty(self, "gtfs_date_bounds")
        self.display_route = IntBoundsProperty(self, "display_route", 0, 3)
        self.stale_cache_days = IntBoundsProperty(self, "stale_cache_days", 0)
        self.name_abbreviations = AbbrevProperty(self, "name_abbreviations")
        self.disable_location_detection = Property(
            self, "disable_location_detection", bool)
        self.disable_connection_detection = Property(
            self, "disable_connection_detection", bool)

    def load_configs(self) -> None:
        # Always load default config first, before loading any custom config
        # or program parameters.
        self.load_config(self.default_config_path)
        for path in _list_configs(self.config_dir):
            if path == self.default_config_path:
                continue
            self.load_config(path)

    def load_config(self, path: Path) -> None:
        """ Load the given config. If no config is given, load the default one.

        :param path: Path to config file, or None to load the default config.
        :return: True, if loading was a success, False if any errors occurred.
        """
        if not path.exists():
            logger.error(f"The given configuration file either does not "
                         f"exist or is not a proper file: '{path}'.")
            quit(err.INVALID_CONFIG_EXIT_CODE)

        data, valid = _read_yaml(path)
        valid &= self._validate_no_invalid_properties(data)
        valid &= self._validate_no_missing_properties()

        if not valid:
            logger.error("Tried to load invalid configuration file "
                         f"'{path}'. Exiting...")
            quit(err.INVALID_CONFIG_EXIT_CODE)

    def load_args(self, args: dict[str, Any]):
        for path in args.pop("config", []):
            self.load_config(Path(path).resolve())

        for name, value in args.items():
            if value is None:
                continue
            if name in self.properties:
                setattr(self, name, value)
                continue
            logger.warning(f"Tried to set unknown property '{name}'.")

    def _validate_no_invalid_properties(self, data: dict[str: Any]) -> bool:
        for key, value in data.items():
            # Even if an item is invalid, continue reading to find all errors.
            try:
                if key not in self.properties:
                    logger.error(f"Invalid config key: {key}")
                    raise err.InvalidPropertyTypeError
                setattr(self, key, value)
            except err.InvalidPropertyTypeError:
                return False
        return True

    def _validate_no_missing_properties(self) -> bool:
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
    def p2g_dir(self) -> Path:
        """ Returns the path, where the src directory is located. """
        return Path(__file__).parents[2]

    @property
    def config_dir(self) -> Path:
        system = platform.system().lower()
        if system == "linux":
            return Path(os.path.expanduser("~/.config/pdf2gtfs/")).resolve()
        if system == "windows":
            return Path(
                os.path.expandvars("%PROGRAMDATA%/pdf2gtfs/")).resolve()
        logger.warning("Currently only windows and linux are fully "
                       "supported.")
        return self.p2g_dir

    @property
    def default_config_path(self) -> Path:
        return self.config_dir.joinpath("config.yaml")

    def _create_default_config(self) -> None:
        self.config_dir.mkdir(parents=True, exist_ok=True)
        if self.default_config_path.exists():
            return
        src = self.p2g_dir.joinpath("config.template.yaml")
        shutil.copy(src, self.default_config_path)
        logger.info(f"Default configuration was created at "
                    f"'{self.default_config_path}'.")

    def __str__(self) -> str:
        string_like = (str, Path)

        def get_property_string(_name: str, _value: Any) -> str:
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
