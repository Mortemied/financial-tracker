"""Useful diagnostics without SQL parameters, user input or secret values."""
import logging
from logging.handlers import RotatingFileHandler
import traceback


class PrivateFormatter(logging.Formatter):
    def formatException(self, info):
        frames = traceback.extract_tb(info[2])
        locations = '\n'.join(f'  {frame.filename}:{frame.lineno} in {frame.name}' for frame in frames)
        return f'{info[0].__name__}\n{locations}'


def configure_logging(directory):
    directory.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(directory / 'application.log', maxBytes=1_000_000,
                                  backupCount=3, encoding='utf-8')
    handler.setFormatter(PrivateFormatter('%(asctime)s %(levelname)s %(name)s: %(message)s'))
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)
