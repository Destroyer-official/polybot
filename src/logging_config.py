"""
Logging infrastructure for Polymarket Arbitrage Bot.

Provides:
- Structured JSON logging
- CloudWatch integration (when AWS credentials available)
- Console logging with color coding
- Multiple log levels
- Context-aware logging
"""

import logging
import json
import sys
from datetime import datetime
from typing import Any, Dict, Optional
from pathlib import Path
import traceback

try:
    import boto3
    import watchtower
    CLOUDWATCH_AVAILABLE = True
except ImportError:
    CLOUDWATCH_AVAILABLE = False

try:
    from colorama import Fore, Style, init as colorama_init
    colorama_init(autoreset=True)
    COLORAMA_AVAILABLE = True
except ImportError:
    COLORAMA_AVAILABLE = False


class JSONFormatter(logging.Formatter):
    """Format log records as JSON for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON string."""
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": traceback.format_exception(*record.exc_info)
            }
        
        # Add extra fields from record
        if hasattr(record, "context"):
            log_data["context"] = record.context
        
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id
        
        if hasattr(record, "component"):
            log_data["component"] = record.component
        
        # Add any custom fields
        for key, value in record.__dict__.items():
            if key not in ["name", "msg", "args", "created", "filename", "funcName",
                          "levelname", "levelno", "lineno", "module", "msecs",
                          "message", "pathname", "process", "processName",
                          "relativeCreated", "thread", "threadName", "exc_info",
                          "exc_text", "stack_info", "context", "request_id", "component"]:
                log_data[key] = value
        
        return json.dumps(log_data)


class ColoredConsoleFormatter(logging.Formatter):
    """Format log records with color coding for console output."""
    
    COLORS = {
        "DEBUG": Fore.BLUE if COLORAMA_AVAILABLE else "",
        "INFO": Fore.GREEN if COLORAMA_AVAILABLE else "",
        "WARNING": Fore.YELLOW if COLORAMA_AVAILABLE else "",
        "ERROR": Fore.RED if COLORAMA_AVAILABLE else "",
        "CRITICAL": Fore.RED + Style.BRIGHT if COLORAMA_AVAILABLE else "",
    }
    
    RESET = Style.RESET_ALL if COLORAMA_AVAILABLE else ""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record with color coding."""
        color = self.COLORS.get(record.levelname, "")
        
        # Format timestamp
        timestamp = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        
        # Format message
        message = record.getMessage()
        
        # Add context if present
        context_str = ""
        if hasattr(record, "context") and record.context:
            context_str = f" | {json.dumps(record.context)}"
        
        # Format final log line
        log_line = f"{color}[{timestamp}] {record.levelname:8s} [{record.name}] {message}{context_str}{self.RESET}"
        
        # Add exception info if present
        if record.exc_info:
            log_line += "\n" + "".join(traceback.format_exception(*record.exc_info))
        
        return log_line


class ContextLogger(logging.LoggerAdapter):
    """Logger adapter that adds context to all log messages."""
    
    def __init__(self, logger: logging.Logger, context: Optional[Dict[str, Any]] = None):
        """Initialize with logger and optional context."""
        super().__init__(logger, context or {})
    
    def process(self, msg: str, kwargs: Dict[str, Any]) -> tuple:
        """Add context to log record."""
        extra = kwargs.get("extra", {})
        extra["context"] = {**self.extra, **extra.get("context", {})}
        kwargs["extra"] = extra
        return msg, kwargs


def setup_logging(
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    cloudwatch_log_group: Optional[str] = None,
    enable_console: bool = True,
    enable_json: bool = False,
) -> logging.Logger:
    """
    Set up logging infrastructure.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional path to log file
        cloudwatch_log_group: Optional CloudWatch log group name
        enable_console: Whether to enable console logging
        enable_json: Whether to use JSON format for file logging
        
    Returns:
        Configured root logger
    """
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    
    # Remove existing handlers
    root_logger.handlers.clear()
    
    # Console handler with color coding
    if enable_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, log_level.upper()))
        console_handler.setFormatter(ColoredConsoleFormatter())
        root_logger.addHandler(console_handler)
    
    # File handler
    if log_file:
        # Create logs directory if it doesn't exist
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(getattr(logging, log_level.upper()))
        
        if enable_json:
            file_handler.setFormatter(JSONFormatter())
        else:
            file_handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S"
                )
            )
        
        root_logger.addHandler(file_handler)
    
    # CloudWatch handler
    if cloudwatch_log_group and CLOUDWATCH_AVAILABLE:
        try:
            cloudwatch_handler = watchtower.CloudWatchLogHandler(
                log_group=cloudwatch_log_group,
                stream_name=f"bot-{datetime.utcnow().strftime('%Y%m%d')}",
                use_queues=True,
                send_interval=5,  # Send logs every 5 seconds
                max_batch_size=10,
                max_batch_count=10,
            )
            cloudwatch_handler.setLevel(getattr(logging, log_level.upper()))
            cloudwatch_handler.setFormatter(JSONFormatter())
            root_logger.addHandler(cloudwatch_handler)
            
            root_logger.info(f"CloudWatch logging enabled: {cloudwatch_log_group}")
        except Exception as e:
            root_logger.warning(f"Failed to set up CloudWatch logging: {e}")
    elif cloudwatch_log_group and not CLOUDWATCH_AVAILABLE:
        root_logger.warning("CloudWatch logging requested but boto3/watchtower not available")
    
    return root_logger


def get_logger(name: str, context: Optional[Dict[str, Any]] = None) -> logging.Logger:
    """
    Get a logger with optional context.
    
    Args:
        name: Logger name (typically __name__)
        context: Optional context dictionary to add to all log messages
        
    Returns:
        Logger or ContextLogger if context provided
    """
    logger = logging.getLogger(name)
    
    if context:
        return ContextLogger(logger, context)
    
    return logger


def log_with_context(
    logger: logging.Logger,
    level: str,
    message: str,
    context: Optional[Dict[str, Any]] = None,
    **kwargs
):
    """
    Log a message with context.
    
    Args:
        logger: Logger instance
        level: Log level (debug, info, warning, error, critical)
        message: Log message
        context: Optional context dictionary
        **kwargs: Additional keyword arguments for logging
    """
    extra = kwargs.get("extra", {})
    if context:
        extra["context"] = context
    kwargs["extra"] = extra
    
    log_method = getattr(logger, level.lower())
    log_method(message, **kwargs)


# Convenience functions for common logging patterns

def log_trade(
    logger: logging.Logger,
    trade_id: str,
    market_id: str,
    strategy: str,
    profit: float,
    status: str,
    **kwargs
):
    """Log a trade execution."""
    context = {
        "trade_id": trade_id,
        "market_id": market_id,
        "strategy": strategy,
        "profit": profit,
        "status": status,
        **kwargs
    }
    log_with_context(logger, "info", f"Trade {status}: {trade_id}", context)


def log_error_with_context(
    logger: logging.Logger,
    error: Exception,
    context: Optional[Dict[str, Any]] = None,
    recovery_action: Optional[str] = None,
):
    """Log an error with full context and recovery action."""
    error_context = {
        "error_type": type(error).__name__,
        "error_message": str(error),
        **(context or {}),
    }
    
    if recovery_action:
        error_context["recovery_action"] = recovery_action
    
    log_with_context(
        logger,
        "error",
        f"Error occurred: {str(error)}",
        error_context,
        exc_info=True
    )


def log_heartbeat(
    logger: logging.Logger,
    health_status: Dict[str, Any],
):
    """Log a heartbeat check."""
    log_with_context(
        logger,
        "info",
        "Heartbeat check",
        health_status
    )


# Example usage
if __name__ == "__main__":
    # Set up logging
    setup_logging(
        log_level="DEBUG",
        log_file="logs/bot.log",
        enable_console=True,
        enable_json=True,
    )
    
    # Get logger
    logger = get_logger(__name__)
    
    # Test different log levels
    logger.debug("This is a debug message")
    logger.info("This is an info message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")
    logger.critical("This is a critical message")
    
    # Test logging with context
    log_with_context(
        logger,
        "info",
        "Trade executed",
        context={
            "trade_id": "trade_123",
            "market_id": "market_456",
            "profit": 0.52,
        }
    )
    
    # Test error logging
    try:
        raise ValueError("Test error")
    except Exception as e:
        log_error_with_context(
            logger,
            e,
            context={"operation": "test"},
            recovery_action="Retry with backoff"
        )
