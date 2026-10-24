"""Log estruturado (uma linha JSON por evento) para execuções de coleta."""
import json
import logging
import sys
from datetime import UTC, datetime

_logger = logging.getLogger("listening")
if not _logger.handlers:
    _handler = logging.StreamHandler(sys.stderr)
    _handler.setFormatter(logging.Formatter("%(message)s"))
    _logger.addHandler(_handler)
    _logger.setLevel(logging.INFO)


def log_event(event: str, **fields) -> None:
    payload = {"ts": datetime.now(UTC).isoformat(), "event": event, **fields}
    _logger.info(json.dumps(payload, ensure_ascii=False, default=str))
