"""
Unit tests for logging infrastructure.

Tests logging setup, formatters, and context logging.
"""

import pytest
import logging
import json
import tempfile
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.logging_config import (
    setup_logging,
    get_logger,
    log_with_context,
    log_trade,
    log_error_with_context,
    JSONFormatter,
    ColoredConsoleFormatter,
)


class TestLoggingSetup:
    """Test logging setup and configuration."""
    
    def test_setup_logging_console_only(self):
        """Test setting up console-only logging."""
        logger = setup_logging(
            log_level="INFO",
            enable_console=True,
        )
        
        assert logger is not None
        assert logger.level == logging.INFO
        assert len(logger.handlers) > 0
    
    def test_setup_logging_with_file(self):
        """Test setting up logging with file output."""
        with tempfile.NamedTemporaryFile(suffix='.log', delete=False) as f:
            log_file = f.name
        
        try:
            logger = setup_logging(
                log_level="DEBUG",
                log_file=log_file,
                enable_console=False,
            )
            
            # Log a test message
            logger.info("Test message")
            
            # Verify file was created and contains message
            assert Path(log_file).exists()
            with open(log_file, 'r') as f:
                content = f.read()
                assert "Test message" in content
        finally:
            # Close all handlers to release file handles
            for handler in logger.handlers[:]:
                handler.close()
                logger.removeHandler(handler)
            Path(log_file).unlink(missing_ok=True)
    
    def test_setup_logging_json_format(self):
        """Test setting up logging with JSON format."""
        with tempfile.NamedTemporaryFile(suffix='.log', delete=False) as f:
            log_file = f.name
        
        try:
            logger = setup_logging(
                log_level="INFO",
                log_file=log_file,
                enable_console=False,
                enable_json=True,
            )
            
            # Log a test message
            logger.info("Test JSON message")
            
            # Verify JSON format
            with open(log_file, 'r') as f:
                line = f.readline()
                log_data = json.loads(line)
                
                assert log_data['message'] == "Test JSON message"
                assert log_data['level'] == "INFO"
                assert 'timestamp' in log_data
        finally:
            # Close all handlers to release file handles
            for handler in logger.handlers[:]:
                handler.close()
                logger.removeHandler(handler)
            Path(log_file).unlink(missing_ok=True)
    
    def test_different_log_levels(self):
        """Test that different log levels work correctly."""
        with tempfile.NamedTemporaryFile(suffix='.log', delete=False) as f:
            log_file = f.name
        
        try:
            # Set up with WARNING level
            logger = setup_logging(
                log_level="WARNING",
                log_file=log_file,
                enable_console=False,
            )
            
            # Log at different levels
            logger.debug("Debug message")  # Should not appear
            logger.info("Info message")    # Should not appear
            logger.warning("Warning message")  # Should appear
            logger.error("Error message")      # Should appear
            
            # Verify only WARNING and above are logged
            with open(log_file, 'r') as f:
                content = f.read()
                assert "Debug message" not in content
                assert "Info message" not in content
                assert "Warning message" in content
                assert "Error message" in content
        finally:
            # Close all handlers to release file handles
            for handler in logger.handlers[:]:
                handler.close()
                logger.removeHandler(handler)
            Path(log_file).unlink(missing_ok=True)


class TestJSONFormatter:
    """Test JSON log formatter."""
    
    def test_json_formatter_basic(self):
        """Test basic JSON formatting."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        
        formatted = formatter.format(record)
        log_data = json.loads(formatted)
        
        assert log_data['message'] == "Test message"
        assert log_data['level'] == "INFO"
        assert log_data['logger'] == "test"
        assert 'timestamp' in log_data
    
    def test_json_formatter_with_context(self):
        """Test JSON formatting with context."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.context = {"trade_id": "123", "profit": 0.5}
        
        formatted = formatter.format(record)
        log_data = json.loads(formatted)
        
        assert log_data['context'] == {"trade_id": "123", "profit": 0.5}
    
    def test_json_formatter_with_exception(self):
        """Test JSON formatting with exception."""
        formatter = JSONFormatter()
        
        try:
            raise ValueError("Test error")
        except ValueError:
            exc_info = sys.exc_info()
        
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=10,
            msg="Error occurred",
            args=(),
            exc_info=exc_info,
        )
        
        formatted = formatter.format(record)
        log_data = json.loads(formatted)
        
        assert 'exception' in log_data
        assert log_data['exception']['type'] == "ValueError"
        assert log_data['exception']['message'] == "Test error"
        assert 'traceback' in log_data['exception']


class TestContextLogging:
    """Test context-aware logging."""
    
    def test_get_logger_with_context(self):
        """Test getting logger with context."""
        logger = get_logger("test", context={"component": "test_component"})
        
        assert logger is not None
        assert hasattr(logger, 'extra')
        assert logger.extra['component'] == "test_component"
    
    def test_log_with_context(self, caplog):
        """Test logging with context."""
        logger = logging.getLogger("test")
        
        with caplog.at_level(logging.INFO):
            log_with_context(
                logger,
                "info",
                "Test message",
                context={"key": "value"}
            )
        
        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert record.message == "Test message"
        assert hasattr(record, 'context')
        assert record.context == {"key": "value"}
    
    def test_log_trade(self, caplog):
        """Test trade logging convenience function."""
        logger = logging.getLogger("test")
        
        with caplog.at_level(logging.INFO):
            log_trade(
                logger,
                trade_id="trade_123",
                market_id="market_456",
                strategy="internal",
                profit=0.52,
                status="success",
            )
        
        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert "trade_123" in record.message
        assert hasattr(record, 'context')
        assert record.context['trade_id'] == "trade_123"
        assert record.context['profit'] == 0.52
    
    def test_log_error_with_context(self, caplog):
        """Test error logging with context."""
        logger = logging.getLogger("test")
        
        try:
            raise ValueError("Test error")
        except ValueError as e:
            with caplog.at_level(logging.ERROR):
                log_error_with_context(
                    logger,
                    e,
                    context={"operation": "test_op"},
                    recovery_action="Retry"
                )
        
        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert "Test error" in record.message
        assert hasattr(record, 'context')
        assert record.context['error_type'] == "ValueError"
        assert record.context['recovery_action'] == "Retry"


class TestColoredConsoleFormatter:
    """Test colored console formatter."""
    
    def test_colored_formatter_basic(self):
        """Test basic colored formatting."""
        formatter = ColoredConsoleFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        
        formatted = formatter.format(record)
        
        assert "Test message" in formatted
        assert "INFO" in formatted
        assert "[test]" in formatted
    
    def test_colored_formatter_with_context(self):
        """Test colored formatting with context."""
        formatter = ColoredConsoleFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.context = {"key": "value"}
        
        formatted = formatter.format(record)
        
        assert "Test message" in formatted
        assert "key" in formatted
        assert "value" in formatted


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
