import logging
from logging.handlers import TimedRotatingFileHandler
import time
import os

def setup_logging():
    # Create a logger
    logger = logging.getLogger("scrapper_logger")
    logger.setLevel(logging.DEBUG)

    # Create a formatter
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

    # Create a TimedRotatingFileHandler and set the rotation interval to 1 day
    log_handler = TimedRotatingFileHandler(f'{os.path.dirname(os.path.realpath(__file__))}\\logs\\scrapper_log.log', when='midnight', interval=1, backupCount=7)
    # when="midnight", interval=1, backupCount=5)
    log_handler.setLevel(logging.DEBUG)
    log_handler.setFormatter(formatter)

    # Add the handler to the logger
    logger.addHandler(log_handler)

    return logger
