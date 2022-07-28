import logging
from logging import LogRecord


def disable_pdfminer_logger():
    """ Disables all pdfminer log output, that is not a warning or worse. """

    def pdfminer_filter(record: LogRecord) -> int:
        return 0 if record.levelno < logging.WARNING else 1

    for name in logging.root.manager.loggerDict:
        # TODO: Check for level and allow warnings/errors.
        if not name.startswith("pdfminer"):
            continue
        logging.getLogger(name).addFilter(pdfminer_filter)


def initialize_logging(level: int):
    disable_pdfminer_logger()
    logging.basicConfig(level=level)
    # FEATURE: Style the log output
