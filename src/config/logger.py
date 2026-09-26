import json
import logging
import os
from datetime import datetime, timezone

from src.config import request_context
from src.util.injection import dependency

# Only emit CloudWatch metrics when running in Lambda -- locally and in tests
# the metric block is just noise.
_IN_LAMBDA = bool(os.getenv("AWS_LAMBDA_FUNCTION_NAME"))
METRIC_NAMESPACE = "Pickem/Api"


class JsonFormatter(logging.Formatter):
    """
    One JSON object per line, so CloudWatch Logs Insights can filter and
    aggregate on fields instead of parsing text.

    Pass structured data with `extra={"fields": {...}}`. Pass
    `extra={"metrics": {name: (value, unit)}}` to also publish CloudWatch
    metrics from the same line via the Embedded Metric Format -- no API calls,
    CloudWatch extracts them from the log.
    """

    def format(self, record: logging.LogRecord) -> str:
        doc = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(
                timespec="milliseconds"
            ),
            "level": record.levelname,
            "location": f"{record.module}.{record.funcName}",
            "message": record.getMessage(),
        }

        ctx = request_context.current()
        if ctx is not None:
            doc["request_id"] = ctx.request_id

        doc.update(getattr(record, "fields", None) or {})

        if record.exc_info:
            doc["exception_type"] = record.exc_info[0].__name__
            doc["exception"] = self.formatException(record.exc_info)

        metrics = getattr(record, "metrics", None)
        if metrics and _IN_LAMBDA:
            doc["_aws"] = {
                "Timestamp": int(record.created * 1000),
                "CloudWatchMetrics": [
                    {
                        "Namespace": METRIC_NAMESPACE,
                        "Dimensions": [["Service"]],
                        "Metrics": [
                            {"Name": name, "Unit": unit}
                            for name, (_, unit) in metrics.items()
                        ],
                    }
                ],
            }
            doc["Service"] = os.getenv("AWS_LAMBDA_FUNCTION_NAME")
            doc.update({name: value for name, (value, _) in metrics.items()})

        return json.dumps(doc, default=str)


@dependency
class Logger(logging.Logger):
    def __init__(self, name: str = __name__):
        """
        Initialize the custom logger with a configuration.
        """

        log_level = os.getenv("LOG_LEVEL", logging.INFO)
        super().__init__(name=name, level=log_level)

        # Set the logging level from the config or default to DEBUG
        self.setLevel(level=log_level)

        # Create a console handler (you could add more handlers as needed)
        ch = logging.StreamHandler()
        ch.setLevel(log_level)
        ch.setFormatter(JsonFormatter())

        # Add the handler to the logger
        self.addHandler(ch)
