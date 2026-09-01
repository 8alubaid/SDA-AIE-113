"""Structured logging: one JSON object per line.

Machines read logs in production, not people. `log.info("model_loaded",
version="v3.2.0")` emits a parseable event with fields, not a sentence that
someone later has to write a regex against.
"""
import json
import logging
from datetime import UTC, datetime
from typing import Any

_LOGGER_NAME = "fraud_service"


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname.lower(),
            "event": record.getMessage(),
        }
        payload.update(getattr(record, "context", {}))
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


class _Log:
    """Thin key-value wrapper over stdlib logging."""

    def __init__(self) -> None:
        self._logger = logging.getLogger(_LOGGER_NAME)

    def _emit(self, level: int, event: str, **fields: Any) -> None:
        self._logger.log(level, event, extra={"context": fields})

    def info(self, event: str, **fields: Any) -> None:
        self._emit(logging.INFO, event, **fields)

    def warning(self, event: str, **fields: Any) -> None:
        self._emit(logging.WARNING, event, **fields)

    def error(self, event: str, exc_info: bool = False, **fields: Any) -> None:
        self._logger.error(
            event, exc_info=exc_info, extra={"context": fields}
        )


log = _Log()


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(_JsonFormatter())

    logger = logging.getLogger(_LOGGER_NAME)
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.setLevel(level.upper())
    logger.propagate = False
