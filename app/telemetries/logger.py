import inspect
import json
import logging
import os
import sys
import threading
import time

from loki_logger_handler.loki_logger_handler import LokiLoggerHandler

# If you want per-request IDs later, you can add a RequestIdManager similar to milli_ai_backend.

grafana_loki_user = os.getenv("GRAFANA_LOKI_USER_ID")
grafana_loki_passowrd = os.getenv("GRAFANA_LOKI_PASSWORD")


class StructuredLogger:
    def __init__(self, name: str, loki_url: str = None, labels: dict = None, loki_enabled: bool = False):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
        self.logger.handlers.clear()

        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(self._get_console_formatter())
        self.logger.addHandler(console_handler)

        # Loki handler
        if loki_enabled and loki_url:
            try:
                loki_handler = LokiLoggerHandler(
                    url=loki_url,
                    labels=labels or {"application": "vami_surat_backend"},
                    timeout=10,
                    enable_self_errors=True,
                    compressed=True,
                    auth=(grafana_loki_user, grafana_loki_passowrd),
                )
                loki_handler.setLevel(logging.INFO)
                loki_handler.setFormatter(self._get_loki_formatter())
                self.logger.addHandler(loki_handler)
                self.loki_connected = True
            except Exception as e:
                self.logger.warning(f"Failed to connect to Loki: {str(e)}. Continuing with console logging only.")
                self.loki_connected = False
        else:
            self.loki_connected = False

    def _get_console_formatter(self):
        """Formatter for console output"""

        class ConsoleFormatter(logging.Formatter):
            def format(self, record):
                log_data = {
                    "timestamp": time.time(),
                    "message": record.getMessage(),
                    "level": record.levelname,
                    "process_id": os.getpid(),
                    "thread_id": threading.get_ident(),
                    "tag": getattr(record, "tag", None),
                }
                return json.dumps(log_data)

        return ConsoleFormatter()

    def _get_loki_formatter(self):
        """Formatter for Loki that returns properly structured data"""

        class LokiFormatter(logging.Formatter):
            def format(self, record):
                log_data = {
                    "timestamp": time.time(),
                    "message": record.getMessage(),
                    "level": record.levelname,
                    "process_id": os.getpid(),
                    "thread_id": threading.get_ident(),
                    "tag": getattr(record, "tag", None),
                }
                # Return tuple: (message_dict, metadata_dict)
                return (log_data, {"level": record.levelname})

        return LokiFormatter()

    def _get_caller_context(self):
        frame = inspect.currentframe().f_back.f_back
        return {
            "funcName": frame.f_code.co_name,
            "lineno": frame.f_lineno,
            "module": inspect.getmodule(frame).__name__ if inspect.getmodule(frame) else "unknown",
        }

    def _prepare_log_message(self, level, *args, **kwargs):
        if args and "message" in kwargs:
            tag = args[0]
            message = kwargs["message"]
        elif args:
            tag = None
            message = args[0]
        else:
            tag = kwargs.get("tag")
            message = kwargs.get("message", "")

        context = self._get_caller_context()
        extra = {
            "tag": tag,
            "caller_funcName": context["funcName"],
            "caller_lineno": context["lineno"],
            "caller_module": context["module"],
        }
        if "request_id" in kwargs:
            extra["request_id"] = kwargs["request_id"]
        return message, extra

    def info(self, *args, **kwargs):
        message, extra = self._prepare_log_message(logging.INFO, *args, **kwargs)
        self.logger.info(message, extra=extra)

    def debug(self, *args, **kwargs):
        message, extra = self._prepare_log_message(logging.DEBUG, *args, **kwargs)
        self.logger.debug(message, extra=extra)

    def warning(self, *args, **kwargs):
        message, extra = self._prepare_log_message(logging.WARNING, *args, **kwargs)
        self.logger.warning(message, extra=extra)

    def error(self, *args, **kwargs):
        exc_info = kwargs.pop("exc_info", False)
        message, extra = self._prepare_log_message(logging.ERROR, *args, **kwargs)
        self.logger.error(message, extra=extra, exc_info=exc_info)

    def critical(self, *args, **kwargs):
        message, extra = self._prepare_log_message(logging.CRITICAL, *args, **kwargs)
        self.logger.critical(message, extra=extra)


# Initialize logger
logger = StructuredLogger(
    name="vami_surat_backend",
    loki_url=os.getenv("GRAFANA_LOKI_URL", "http://localhost:3100/loki/api/v1/push"),
    labels={"application": "vami_surat_backend"},
    loki_enabled=os.getenv("LOKI_ENABLED", "false") == "true",
)


