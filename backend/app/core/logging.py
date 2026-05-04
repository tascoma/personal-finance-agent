import logging
import logging.handlers
from pathlib import Path

from app.core.config import settings

_LOG_DIR = Path(__file__).resolve().parents[2] / "logs"
_FMT = "%(asctime)s %(levelname)s %(name)s %(message)s"
_DATEFMT = "%Y-%m-%dT%H:%M:%S"


def configure_logging() -> None:
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    _LOG_DIR.mkdir(exist_ok=True)

    file_handler = logging.handlers.RotatingFileHandler(
        _LOG_DIR / "app.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
    )
    file_handler.setFormatter(logging.Formatter(_FMT, datefmt=_DATEFMT))

    logging.basicConfig(
        level=level,
        format=_FMT,
        datefmt=_DATEFMT,
        handlers=[logging.StreamHandler(), file_handler],
    )
