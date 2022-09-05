INVALID_CONFIG_EXIT_CODE = 1


# TODO: Add basic messages to each exception


class PropertyException(BaseException):
    pass


class InvalidPropertyTypeError(PropertyException):
    pass


class MissingRequiredPropertyError(PropertyException):
    pass


class InvalidHolidayCode(PropertyException):
    pass


class InvalidHeaderDays(PropertyException):
    pass


class InvalidRouteTypeValue(PropertyException):
    pass


class InvalidOutputDirectory(PropertyException):
    pass


class InvalidDateBoundsError(PropertyException):
    pass


class OutOfBoundsPropertyError(PropertyException):
    pass


class InvalidRepeatIdentifier(PropertyException):
    pass
