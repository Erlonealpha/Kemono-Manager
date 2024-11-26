import logging
from rich.logging import RichHandler
from pathlib import Path
from os import makedirs


def get_logger(name, level=logging.INFO, console=True, log_file=None):
    logger = logging.getLogger(name)
    logger.setLevel(level)

    
    if console:
        console_handler = RichHandler()
        console_handler.setLevel(level)
        # console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    if log_file:
        formatter = logging.Formatter('[%(levelname)s]%(asctime)s %(module)s.%(funcName)s:%(lineno)d %(message)s')
        try:
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
        except FileNotFoundError:
            path = Path(log_file).parent
            makedirs(path, exist_ok=True)
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(formatter)
        file_handler.setLevel(level)
        logger.addHandler(file_handler)

    return logger

logger = get_logger(__name__, logging.DEBUG, console=True, log_file='logs/log.txt')
logger.setLevel(logging.INFO)