import os
import logging
import platform
from pathlib import Path
from tempfile import mkdtemp

from custom_conf.config import BaseConfig
from custom_conf.properties.property import Property
from custom_conf.properties.bounded_property import (
    FloatBoundedProperty, IntBoundedProperty,
    )
from custom_conf.properties.nested_property import NestedTypeProperty

from pdf2gtfs.config.properties import (
    AbbrevProperty, AverageSpeedProperty, DateBoundsProperty,
    DirectionProperty, FilenameProperty,
    HeaderValuesProperty, HolidayCodeProperty, InputProperty,
    OutputPathProperty, PagesProperty, RepeatIdentifierProperty,
    RouteTypeProperty, SplitOrientationsProperty,
    )


logger = logging.getLogger(__name__)


class P2GConfig(BaseConfig):
    def __init__(self, load_default=True, load_all=True) -> None:
        self._temp_dir: Path | None = None
        super().__init__(load_default, load_all)

    @property
    def output_dir(self) -> Path:
        if self.output_path.name.endswith(".zip"):
            return self.output_path.parent
        return self.output_path

    @property
    def config_dir(self) -> Path:
        """ Return the config directory, based on what system is running. """
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
    def p2g_dir(self) -> Path:
        return Path(__file__).parents[1]

    @property
    def default_config_path(self) -> Path:
        return self.p2g_dir.joinpath("config.template.yaml")

    @property
    def temp_dir(self) -> Path:
        """ The path to the temporary directory used by pdf2gtfs. """
        if not self._temp_dir:
            self._temp_dir = Path(mkdtemp(prefix="pdf2gtfs-"))
        return self._temp_dir

    def _initialize_config_properties(self) -> None:
        self.time_format = Property("time_format", str)
        self.header_values = HeaderValuesProperty("header_values")
        self.negative_header_values = \
            NestedTypeProperty("negative_header_values", list[str])
        self.holiday_code = HolidayCodeProperty("holiday_code")
        self.repeat_identifier = RepeatIdentifierProperty("repeat_identifier")
        self.repeat_strategy = Property("repeat_strategy", str)
        self.pages = PagesProperty("pages")
        self.max_row_distance = IntBoundedProperty("max_row_distance", 0)
        self.min_row_count = IntBoundedProperty("min_row_count", 0)
        self.filename = FilenameProperty("filename", str)
        self.annot_identifier = Property("annot_identifier", list)
        self.route_identifier = Property("route_identifier", list)
        self.gtfs_routetype = RouteTypeProperty("gtfs_routetype")
        self.average_speed = AverageSpeedProperty("average_speed")
        self.allowed_stop_chars = Property("allowed_stop_chars", list)
        self.output_path = OutputPathProperty("output_path")
        self.preprocess = Property("preprocess", bool)
        self.output_pp = Property("output_pp", bool)
        self.non_interactive = Property("non_interactive", bool)
        self.gtfs_date_bounds = DateBoundsProperty("gtfs_date_bounds")
        self.display_route = IntBoundedProperty("display_route", 0, 7)
        self.stale_cache_days = IntBoundedProperty("stale_cache_days", 0)
        self.name_abbreviations = AbbrevProperty("name_abbreviations")
        self.disable_location_detection = \
            Property("disable_location_detection", bool)
        self.min_connection_count = Property("min_connection_count", int)
        self.arrival_identifier = \
            NestedTypeProperty("arrival_identifier", list[str])
        self.departure_identifier = \
            NestedTypeProperty("departure_identifier", list[str])
        self.interpolate_missing_locations = \
            Property("interpolate_missing_locations", bool)
        self.min_travel_distance = IntBoundedProperty("min_travel_distance", 0)
        self.average_travel_distance_offset = \
            IntBoundedProperty("average_travel_distance_offset", 1)
        self.simple_travel_cost_calculation = \
            Property("simple_travel_cost_calculation", bool)
        self.missing_node_cost = IntBoundedProperty("missing_node_cost", 0)
        self.disable_close_node_check = \
            Property("disable_close_node_check", bool)
        self.max_char_distance = FloatBoundedProperty("max_char_distance", 0.)
        self.cache_directory = Property("cache_directory", str)
        self.qlever_endpoint_url = Property("qlever_endpoint_url", str)
        self.input_files = InputProperty("input_files")
        self.table_expansion_directions = \
            DirectionProperty("table_expansion_directions")
        self.extra_greedy = Property("extra_greedy", bool)
        self.use_legacy_extraction = Property("use_legacy_extraction", bool)
        self.stop_min_mean_normed_length = \
            IntBoundedProperty("stop_min_mean_normed_length", 0)
        self.stop_letter_ratio = FloatBoundedProperty(
            "stop_letter_ratio", 0., 1.)
        self.min_cell_overlap = FloatBoundedProperty(
            "min_cell_overlap", 0., 1.)
        self.merge_split_tables = Property("merge_split_tables", bool)
        self.split_orientations = SplitOrientationsProperty(
            "split_orientations")

        super()._initialize_config_properties()


Config = P2GConfig()
