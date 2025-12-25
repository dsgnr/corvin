import logging
import logging.config

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "[%(asctime)s +0000] [%(process)d] [%(levelname)s] %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stderr",
            "formatter": "standard",
        },
    },
    "root": {
        "level": "INFO",
        "handlers": ["console"],
    },
    "loggers": {
        "apscheduler": {
            "level": "WARNING",
        },
    },
}


def setup_logging(level: int = logging.INFO) -> None:
    """Configure application-wide logging."""
    logging.config.dictConfig(LOGGING_CONFIG)
    logging.getLogger().setLevel(level)


def get_logger(name: str) -> logging.Logger:
    """Return a logger instance prefixed with 'app.' for the given module name."""
    return logging.getLogger(f"app.{name}")
