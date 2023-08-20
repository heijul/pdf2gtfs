""" Functions to setup logging. """

import logging
import sys
from logging import LogRecord


def disable_pdfminer_logger() -> None:
    """ Disables all pdfminer log output, that is not a Warning or worse. """

    def pdfminer_filter(record: LogRecord) -> int:
        """ Filter too verbose pdfminer messages.

        Checks if the level of severity of the record is more severe
        than a warning. If not, the message will not be logged.
        """
        return 0 if record.levelno < logging.WARNING else 1

    for name in logging.root.manager.loggerDict:
        if not name.startswith("pdfminer"):
            continue
        logging.getLogger(name).addFilter(pdfminer_filter)


def initialize_logging(level: int, *,
                       force: bool = False, handlers: list = None) -> None:
    """ Reduce the pdfminer output and setup basic logging. """
    disable_pdfminer_logger()
    if handlers is None:
        handlers = [logging.StreamHandler(stream=sys.stdout)]
    logging.basicConfig(level=level, force=force, handlers=handlers)


def flush_all_loggers() -> None:
    """ Flush all handlers, to ensure all messages are displayed. """
    for handler in logging.getLogger().handlers:
        handler.flush()
