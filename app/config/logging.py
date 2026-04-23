from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    def __init__(self, *, service_name: str, environment: str) -> None:
        super().__init__()
        self.service_name = service_name
        self.environment = environment

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": self.service_name,
            "environment": self.environment,
        }

        for field in (
            "provider",
            "aws_region",
            "target_id",
            "target_kind",
            "target_source",
            "request_id",
            "latency_ms",
            "stop_reason",
            "service_tier",
            "input_tokens",
            "output_tokens",
            "guardrail_mode",
            "guardrail_identifier",
            "guardrail_applied",
            "guardrail_intervened",
            "error_code",
            "details",
        ):
            if hasattr(record, field):
                payload[field] = getattr(record, field)

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)


def configure_logging(*, level: str, service_name: str, environment: str) -> None:
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(level.upper())

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        JsonFormatter(service_name=service_name, environment=environment)
    )
    root_logger.addHandler(handler)

    # Keep third-party SDK chatter out of normal CLI output unless the user
    # explicitly turns the application log level down to DEBUG and inspects them separately.
    for logger_name in ("boto3", "botocore", "urllib3"):
        logging.getLogger(logger_name).setLevel(logging.WARNING)
