import logging
import logging.handlers
from contextvars import ContextVar
from pathlib import Path

from app.core.config import settings

_LOG_DIR = Path(__file__).resolve().parents[2] / "logs"
_FMT = "%(asctime)s %(levelname)s [%(request_id)s] %(name)s %(message)s"
_DATEFMT = "%Y-%m-%dT%H:%M:%S"

# Set per-request by RequestIdMiddleware (in app.main). Default keeps logs
# emitted outside an HTTP request (startup/shutdown) parseable.
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")


class _RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get()
        return True


class _NoHealthCheck(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return "GET /health" not in record.getMessage()


def configure_logging() -> None:
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    _LOG_DIR.mkdir(exist_ok=True)

    file_handler = logging.handlers.RotatingFileHandler(
        _LOG_DIR / "app.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
    )
    file_handler.setFormatter(logging.Formatter(_FMT, datefmt=_DATEFMT))

    rid_filter = _RequestIdFilter()
    stream_handler = logging.StreamHandler()
    for handler in (file_handler, stream_handler):
        handler.addFilter(rid_filter)

    logging.basicConfig(
        level=level,
        format=_FMT,
        datefmt=_DATEFMT,
        handlers=[stream_handler, file_handler],
    )

    logging.getLogger("uvicorn.access").addFilter(_NoHealthCheck())
