import json
import logging
import sys
from datetime import UTC, datetime

from app.core.context import get_current_context


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        ctx = get_current_context()
        log_entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": ctx.request_id if ctx else None,
            "user_id": str(ctx.user_id) if ctx and ctx.user_id else None,
        }
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry)


def setup_logging(level: int = logging.INFO) -> None:
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Avoid duplicate handlers
    if not any(isinstance(h.formatter, JsonFormatter) for h in root_logger.handlers):
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        root_logger.handlers = [handler]
