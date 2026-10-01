"""Application logging setup.

Routes our ``app.*`` loggers to the console so stage activity (cloning,
discovery, etc.) is visible in the backend terminal alongside uvicorn's own
request logs.
"""

from __future__ import annotations

import logging

_CONFIGURED = False


_CLEAN_LOGGERS = {"auth", "connect", "strategy", "migration", "discovery"}


class ApexConsoleFormatter(logging.Formatter):
    """Console formatter that omits logger name for application log entries."""

    def __init__(self) -> None:
        super().__init__(datefmt="%H:%M:%S")
        self._standard_fmt = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
            datefmt="%H:%M:%S",
        )
        self._clean_fmt = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-7s | %(message)s",
            datefmt="%H:%M:%S",
        )

    def format(self, record: logging.LogRecord) -> str:
        if record.name in _CLEAN_LOGGERS:
            return self._clean_fmt.format(record)
        return self._standard_fmt.format(record)


def configure_logging(level: int = logging.INFO) -> None:
    """Attach a console handler to application loggers (idempotent)."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    handler = logging.StreamHandler()
    handler.setFormatter(ApexConsoleFormatter())

    targets = ("app", *_CLEAN_LOGGERS)
    for logger_name in targets:
        logger = logging.getLogger(logger_name)
        logger.addHandler(handler)
        logger.setLevel(level)
        logger.propagate = False

    _CONFIGURED = True
