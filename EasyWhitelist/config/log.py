import logging

LOG_FORMAT = "%(asctime)s-%(process)d-%(filename)s:%(lineno)d-%(levelname)s-%(message)s"


def set_log(verbose: int = 0):

    level_map = {
        0: logging.WARNING,
        1: logging.INFO,
        2: logging.DEBUG
    }

    level = level_map.get(verbose, logging.WARNING)

    logging.basicConfig(level=level, format=LOG_FORMAT)
