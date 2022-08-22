INVALID_CONFIG_EXIT_CODE = 1


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
