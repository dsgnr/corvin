import logging
import sys


def setup_logging(level: int = logging.INFO) -> None:
    """Configure application-wide logging with a consistent format."""
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(handler)

    logging.getLogger("apscheduler").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return a logger instance prefixed with 'app.' for the given module name."""
    return logging.getLogger(f"app.{name}")
