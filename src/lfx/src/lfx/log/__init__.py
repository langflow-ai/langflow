"""Logging module for lfx package."""

from lfx.log._streams import make_streams_resilient
from lfx.log.logger import configure, logger

make_streams_resilient()

__all__ = ["configure", "logger"]
