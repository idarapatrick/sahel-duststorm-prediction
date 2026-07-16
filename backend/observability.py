"""Small JSON logging helpers suitable for Render log streams."""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone


def configure_logging() -> logging.Logger:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    return logging.getLogger("sahelwatch")


def log_event(logger: logging.Logger, event: str, **fields) -> None:
    logger.info(json.dumps({
        "timestamp": datetime.now(timezone.utc).isoformat(), "event": event, **fields,
    }, default=str, separators=(",", ":")))

