"""Structured logging setup for the Study Task Tracker.

Uses structlog with a TTY-aware renderer: human-readable console output on an
interactive terminal, JSON otherwise (for CI or log aggregation). All logs go
to stderr so stdout stays reserved for command output (OBS-04). Log calls use
key/value pairs — never f-strings — so values such as the database password
are never embedded in a formatted message (SEC-03, ruff ``G004``).
"""

from __future__ import annotations

import logging
import sys

import structlog


def configure_logging(level: str = "WARNING") -> None:
    """Configure structlog for the application.

    Args:
        level: Minimum level name to emit (e.g. ``"INFO"``, ``"WARNING"``).
            Unknown names fall back to ``WARNING``.
    """
    renderer: structlog.types.Processor = (
        structlog.dev.ConsoleRenderer()
        if sys.stderr.isatty()
        else structlog.processors.JSONRenderer()
    )
    min_level = getattr(logging, level.upper(), logging.WARNING)

    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(min_level),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )
