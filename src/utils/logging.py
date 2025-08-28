import logging

from rich.logging import RichHandler

from config.config import settings


def setup_logging():
    handler = RichHandler(
        rich_tracebacks=True,
        markup=True,
        show_time=True,
        show_level=True,
        show_path=True,
        log_time_format=settings.log.datefmt,
        omit_repeated_times=True,
    )
    root = logging.getLogger()
    level = getattr(logging, str(settings.log.level), None)
    if not isinstance(level, int):
        level = logging.INFO
    root.setLevel(level)
    root.handlers = [handler]


setup_logging()
