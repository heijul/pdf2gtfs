INVALID_CONFIG_EXIT_CODE = 1


# TODO: Add basic messages to each exception


class PropertyError(Exception):
    pass


class InvalidPropertyTypeError(PropertyError):
    pass


class MissingRequiredPropertyError(PropertyError):
    pass


class InvalidHolidayCodeError(PropertyError):
    pass


class InvalidHeaderDaysError(PropertyError):
    pass


class InvalidRouteTypeValueError(PropertyError):
    pass


class InvalidOutputDirectoryError(PropertyError):
    pass


class InvalidDateBoundsError(PropertyError):
    pass


class OutOfBoundsPropertyError(PropertyError):
    pass


class InvalidRepeatIdentifierError(PropertyError):
    pass


class UnknownPropertyError(PropertyError):
    pass
