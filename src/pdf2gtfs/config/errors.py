""" Exceptions raised by properties. """
from custom_conf.errors import PropertyError


class InvalidHolidayCodeError(PropertyError):
    """ Raised, if the given country or subdivision code was not found. """
    pass


class InvalidHeaderDaysError(PropertyError):
    """ Raised, if the given header_values is of the wrong format. """
    pass


class InvalidRouteTypeValueError(PropertyError):
    """ Raised, if the given routetype does not exist. """
    pass


class InvalidOutputPathError(PropertyError):
    """ Raised, if the output directory exists and is not a directory. """
    pass


class InvalidDateBoundsError(PropertyError):
    """ Raised, if the given date bounds are not proper years. """
    pass


class InvalidRepeatIdentifierError(PropertyError):
    """ Raised, if the given repeat_identifier does not consist of lists
     of two strings. """
    pass


class InvalidDirectionError(PropertyError):
    def __init__(self, **kwargs) -> None:
        """ Raised if any of the given directions is not a valid direction.

        :keyword prop: The property that was created.
        :type prop: Property
        :keyword direction: The invalid direction char.
        :type direction: str
        """
        if "prop" not in kwargs or "direction" not in kwargs:
            super().__init__()
            return
        prop_name = kwargs["prop"].name
        direction = kwargs["direction"]
        msg = (f"Tried to use invalid direction '{direction}' for the "
               f"property '{prop_name}'. Each direction needs to be one of "
               f"'N', 'W', 'S' or 'E'.")
        super().__init__(msg)
