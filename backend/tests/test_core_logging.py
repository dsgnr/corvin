"""Tests for core logging module."""

import logging

from app.core.logging import get_logger, setup_logging


class TestGetLogger:
    """Tests for get_logger function."""

    def test_returns_logger(self):
        """Should return a logger instance."""
        logger = get_logger("test")

        assert isinstance(logger, logging.Logger)

    def test_prefixes_with_app(self):
        """Should prefix logger name with 'app.'."""
        logger = get_logger("mymodule")

        assert logger.name == "app.mymodule"

    def test_different_names_return_different_loggers(self):
        """Should return distinct loggers for different names."""
        logger1 = get_logger("module1")
        logger2 = get_logger("module2")

        assert logger1.name != logger2.name


class TestSetupLogging:
    """Tests for setup_logging function."""

    def test_configures_root_logger(self):
        """Should configure root logger with INFO level."""
        setup_logging()

        root = logging.getLogger()
        assert root.level == logging.INFO

    def test_suppresses_apscheduler(self):
        """Should set apscheduler to WARNING level."""
        setup_logging()

        apscheduler_logger = logging.getLogger("apscheduler")
        assert apscheduler_logger.level == logging.WARNING
