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
