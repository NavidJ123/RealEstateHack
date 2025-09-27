"""Logging utilities with structured output for the AI Broker backend."""

from __future__ import annotations

import logging
import os
from typing import Optional

_LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()


def configure_logging(namespace: str = "backend") -> logging.Logger:
    """Return a namespaced logger configured for structured output.

    The logger prints log messages as single-line records with key=value pairs so
    that they can be ingested by log aggregators while still being human readable.
    """

    logger = logging.getLogger(namespace)
    if logger.handlers:
        return logger

    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    handler.setFormatter(formatter)

    logger.addHandler(handler)
    logger.setLevel(_LOG_LEVEL)
    logger.propagate = False
    return logger


def get_logger(child: Optional[str] = None) -> logging.Logger:
    """Helper to retrieve a child logger."""

    base = configure_logging()
    if child:
        return base.getChild(child)
    return base

