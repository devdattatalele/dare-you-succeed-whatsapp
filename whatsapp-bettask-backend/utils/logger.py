"""
Logging utility for WhatsApp BetTask Backend.

Provides centralized logging configuration and setup.
"""

import logging
import logging.config
import sys
from typing import Optional

from config.settings import settings

def setup_logger(name: str) -> logging.Logger:
    """
    Set up a logger with the given name.
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        logging.Logger: Configured logger instance
    """
    # Configure logging if not already done
    if not hasattr(setup_logger, '_configured'):
        logging.config.dictConfig(settings.get_log_config())
        setup_logger._configured = True
    
    return logging.getLogger(name)

def log_request(logger: logging.Logger, request_id: str, method: str, path: str, user_id: Optional[str] = None):
    """
    Log incoming request.
    
    Args:
        logger: Logger instance
        request_id: Unique request ID
        method: HTTP method
        path: Request path
        user_id: Optional user ID
    """
    user_info = f" [User: {user_id}]" if user_id else ""
    logger.info(f"[{request_id}] {method} {path}{user_info}")

def log_response(logger: logging.Logger, request_id: str, status_code: int, duration_ms: float):
    """
    Log response.
    
    Args:
        logger: Logger instance
        request_id: Unique request ID
        status_code: HTTP status code
        duration_ms: Request duration in milliseconds
    """
    logger.info(f"[{request_id}] Response: {status_code} ({duration_ms:.2f}ms)")

def log_whatsapp_message(logger: logging.Logger, direction: str, phone: str, message_type: str, content_preview: str):
    """
    Log WhatsApp message activity.
    
    Args:
        logger: Logger instance
        direction: 'incoming' or 'outgoing'
        phone: Phone number
        message_type: Type of message
        content_preview: Preview of message content
    """
    masked_phone = phone[:3] + "****" + phone[-4:] if len(phone) > 7 else phone
    logger.info(f"WhatsApp {direction} [{message_type}] {masked_phone}: {content_preview}")

def log_ai_interaction(logger: logging.Logger, operation: str, confidence: float, result: str):
    """
    Log AI interaction.
    
    Args:
        logger: Logger instance
        operation: AI operation type
        confidence: Confidence score
        result: Result summary
    """
    logger.info(f"AI {operation} (conf: {confidence:.2f}): {result}")

def log_database_operation(logger: logging.Logger, operation: str, table: str, duration_ms: float, success: bool):
    """
    Log database operation.
    
    Args:
        logger: Logger instance
        operation: Database operation type
        table: Table name
        duration_ms: Operation duration
        success: Whether operation succeeded
    """
    status = "SUCCESS" if success else "FAILED"
    logger.info(f"DB {operation} {table} [{status}] ({duration_ms:.2f}ms)")

class RequestLogger:
    """Context manager for request logging."""
    
    def __init__(self, logger: logging.Logger, request_id: str, method: str, path: str, user_id: Optional[str] = None):
        self.logger = logger
        self.request_id = request_id
        self.method = method
        self.path = path
        self.user_id = user_id
        self.start_time = None
    
    def __enter__(self):
        import time
        self.start_time = time.time()
        log_request(self.logger, self.request_id, self.method, self.path, self.user_id)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        import time
        duration_ms = (time.time() - self.start_time) * 1000
        status_code = 500 if exc_type else 200
        log_response(self.logger, self.request_id, status_code, duration_ms)

class DatabaseLogger:
    """Context manager for database operation logging."""
    
    def __init__(self, logger: logging.Logger, operation: str, table: str):
        self.logger = logger
        self.operation = operation
        self.table = table
        self.start_time = None
    
    def __enter__(self):
        import time
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        import time
        duration_ms = (time.time() - self.start_time) * 1000
        success = exc_type is None
        log_database_operation(self.logger, self.operation, self.table, duration_ms, success) 