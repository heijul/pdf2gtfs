import logging
import os.path
import platform
from pathlib import Path
from typing import Any

from yaml import safe_load, YAMLError
from yaml.scanner import ScannerError

import config.errors as err
import config.properties as p


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
    if not directory.is_dir():
        logger.warning(f"Could not find configuration files in "
                       f"{directory}, because it is not a directory.")
        return []
    return list(directory.glob("*.yaml")) + list(directory.glob("*.yml"))


class _Config(InstanceDescriptorMixin):
    def __init__(self) -> None:
        self._create_config_dir()
        self._initialize_config_properties()
        # Always load default config first, before loading any custom config
        # or program parameters.
        self.load_default_config()
        self.load_configs(self.config_dir)

    def _initialize_config_properties(self) -> None:
        self.properties = []
        self.time_format = p.Property(self, "time_format", str)
        self.header_values = p.HeaderValuesProperty(self, "header_values")
        self.holiday_code = p.HolidayCodeProperty(self, "holiday_code")
        self.repeat_identifier = p.RepeatIdentifierProperty(
            self, "repeat_identifier")
        self.repeat_strategy = p.Property(self, "repeat_strategy", str)
        self.pages = p.PagesProperty(self, "pages")
        self.max_row_distance = p.IntBoundsProperty(
            self, "max_row_distance", 0)
        self.min_row_count = p.IntBoundsProperty(self, "min_row_count", 0)
        self.filename = p.FilenameProperty(self, "filename", str)
        self.annot_identifier = p.Property(self, "annot_identifier", list)
        self.route_identifier = p.Property(self, "route_identifier", list)
        self.gtfs_routetype = p.RouteTypeProperty(self, "gtfs_routetype")
        self.allowed_stop_chars = p.Property(self, "allowed_stop_chars", list)
        self.max_stop_distance = p.IntBoundsProperty(
            self, "max_stop_distance", 0)
        self.output_dir = p.OutputDirectoryProperty(self, "output_dir")
        self.preprocess = p.Property(self, "preprocess", bool)
        self.output_pp = p.Property(self, "output_pp", bool)
        self.always_overwrite = p.Property(self, "always_overwrite", bool)
        self.non_interactive = p.Property(self, "non_interactive", bool)
        self.gtfs_date_bounds = p.DateBoundsProperty(self, "gtfs_date_bounds")
        self.display_route = p.IntBoundsProperty(self, "display_route", 0, 3)
        self.stale_cache_days = p.IntBoundsProperty(self, "stale_cache_days", 0)
        self.name_abbreviations = p.AbbrevProperty(self, "name_abbreviations")
        self.disable_location_detection = p.Property(
            self, "disable_location_detection", bool)
        self.min_connection_count = p.Property(
            self, "min_connection_count", int)
        self.arrival_identifier = p.NestedTypeProperty(
            self, "arrival_identifier", list[str])
        self.departure_identifier = p.NestedTypeProperty(
            self, "departure_identifier", list[str])

    def load_default_config(self) -> None:
        if not self.load_config(self.default_config_path):
            logger.error("Errors occurred when reading the given configs. "
                         "Exiting...")
            quit(err.INVALID_CONFIG_EXIT_CODE)

    def load_configs(self, path: Path) -> None:
        configs = [path] if path.is_file() else _list_configs(path)
        if not configs:
            return

        valid = True
        for path in configs:
            if path == self.default_config_path:
                continue
            valid &= self.load_config(path)
        valid &= self._validate_no_missing_properties()
        if valid:
            return

        logger.error(
            "Errors occurred when reading the given configs. Exiting...")
        quit(err.INVALID_CONFIG_EXIT_CODE)

    def load_config(self, path: Path) -> bool:
        """ Load the given config.

        :param path: Path to config file.
        :return: True, if loading was a success, False if any errors occurred.
        """
        if path.exists() and path.is_file():
            data, valid = _read_yaml(path)
            valid &= self._validate_no_invalid_properties(data)
            return valid

        logger.error(f"The given configuration file either does not "
                     f"exist or is not a proper file: '{path}'.")
        return False

    def load_args(self, args: dict[str, Any]):
        for config_path in args.pop("config", []):
            path = Path(config_path).resolve()
            if path.is_dir():
                logger.info(
                    f"The given config path '{path}' leads to a directory. "
                    f"All configs in the directory will be read.")
                self.load_configs(path)
            else:
                self.load_config(path)

        for name, value in args.items():
            if value is None:
                # Nothing to log, cause this just means argument is unset.
                continue
            if name not in self.properties:
                logger.error(f"Tried to set unknown property '{name}'.")
                continue
            setattr(self, name, value)

    def _validate_no_invalid_properties(self, data: dict[str: Any]) -> bool:
        valid = True
        for key, value in data.items():
            # Even if an item is invalid, continue reading to find all errors.
            try:
                if key not in self.properties:
                    logger.error(f"Invalid config key: {key}")
                    raise err.UnknownPropertyError
                setattr(self, key, value)
            except err.PropertyError:
                valid = False
        return valid

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
        return self.p2g_dir.joinpath("config.template.yaml")

    def _create_config_dir(self) -> None:
        if self.config_dir.exists():
            return
        self.config_dir.mkdir(parents=True, exist_ok=True)

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
