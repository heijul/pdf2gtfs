""" Exceptions raised by properties. """

INVALID_CONFIG_EXIT_CODE = 1


class PropertyError(Exception):
    """ Base class for exceptions raised by properties. """
    pass


class InvalidPropertyTypeError(PropertyError):
    """ Raised, if the type of a value differs from the properties type. """
    pass


class MissingRequiredPropertyError(PropertyError):
    """ Raised, if a required property is missing.
    Currently all properties are required. """
    pass


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


class OutOfBoundsPropertyError(PropertyError):
    """ Raised, if the given value of a bounded property is out of bounds. """
    pass


class InvalidRepeatIdentifierError(PropertyError):
    """ Raised, if the given repeat_identifier does not consist of lists
     of two strings. """
    pass


class UnknownPropertyError(PropertyError):
    """ Raised, when trying to set a property that does not exist.
    Usually this happens, when the name was missspelled. """
    pass
