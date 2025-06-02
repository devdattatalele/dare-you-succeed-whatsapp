"""
Error handling utilities for WhatsApp BetTask Backend.

Provides centralized error handling and custom exceptions.
"""

import logging
from typing import Dict, Any, Optional
import traceback
from fastapi import HTTPException
from fastapi.responses import JSONResponse

from utils.logger import setup_logger

logger = setup_logger(__name__)

class BetTaskError(Exception):
    """Base exception for BetTask application."""
    
    def __init__(self, message: str, error_code: str = "BETTASK_ERROR", details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)

class ValidationError(BetTaskError):
    """Raised when input validation fails."""
    
    def __init__(self, message: str, field: str = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "VALIDATION_ERROR", details)
        self.field = field

class InsufficientBalanceError(BetTaskError):
    """Raised when user has insufficient balance."""
    
    def __init__(self, required: float, available: float):
        message = f"Insufficient balance. Required: ₹{required:.2f}, Available: ₹{available:.2f}"
        details = {"required": required, "available": available}
        super().__init__(message, "INSUFFICIENT_BALANCE", details)

class ChallengeNotFoundError(BetTaskError):
    """Raised when challenge is not found."""
    
    def __init__(self, challenge_id: str):
        message = f"Challenge not found: {challenge_id}"
        details = {"challenge_id": challenge_id}
        super().__init__(message, "CHALLENGE_NOT_FOUND", details)

class VerificationError(BetTaskError):
    """Raised when proof verification fails."""
    
    def __init__(self, message: str, confidence: float = 0.0, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "VERIFICATION_ERROR", details)
        self.confidence = confidence

class AIServiceError(BetTaskError):
    """Raised when AI service encounters an error."""
    
    def __init__(self, message: str, service: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "AI_SERVICE_ERROR", details)
        self.service = service

class DatabaseError(BetTaskError):
    """Raised when database operation fails."""
    
    def __init__(self, message: str, operation: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "DATABASE_ERROR", details)
        self.operation = operation

class WhatsAppError(BetTaskError):
    """Raised when WhatsApp operation fails."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "WHATSAPP_ERROR", details)

def handle_error(error: Exception) -> JSONResponse:
    """
    Handle errors and return appropriate JSON response.
    
    Args:
        error: Exception that occurred
        
    Returns:
        JSONResponse: Formatted error response
    """
    try:
        # Log the full error with traceback
        logger.error(f"Error occurred: {error}", exc_info=True)
        
        # Handle custom BetTask errors
        if isinstance(error, BetTaskError):
            return JSONResponse(
                status_code=400,
                content={
                    "error": True,
                    "error_code": error.error_code,
                    "message": error.message,
                    "details": error.details
                }
            )
        
        # Handle FastAPI HTTP exceptions
        elif isinstance(error, HTTPException):
            return JSONResponse(
                status_code=error.status_code,
                content={
                    "error": True,
                    "error_code": "HTTP_ERROR",
                    "message": error.detail,
                    "details": {}
                }
            )
        
        # Handle validation errors
        elif "validation" in str(error).lower():
            return JSONResponse(
                status_code=422,
                content={
                    "error": True,
                    "error_code": "VALIDATION_ERROR",
                    "message": "Input validation failed",
                    "details": {"original_error": str(error)}
                }
            )
        
        # Handle database connection errors
        elif any(keyword in str(error).lower() for keyword in ["connection", "timeout", "database"]):
            return JSONResponse(
                status_code=503,
                content={
                    "error": True,
                    "error_code": "SERVICE_UNAVAILABLE",
                    "message": "Service temporarily unavailable. Please try again later.",
                    "details": {}
                }
            )
        
        # Handle network/API errors
        elif any(keyword in str(error).lower() for keyword in ["network", "connection", "timeout"]):
            return JSONResponse(
                status_code=502,
                content={
                    "error": True,
                    "error_code": "NETWORK_ERROR",
                    "message": "Network error occurred. Please try again.",
                    "details": {}
                }
            )
        
        # Generic error handling
        else:
            return JSONResponse(
                status_code=500,
                content={
                    "error": True,
                    "error_code": "INTERNAL_ERROR",
                    "message": "An internal error occurred. Please try again later.",
                    "details": {}
                }
            )
            
    except Exception as e:
        # Fallback error handling
        logger.critical(f"Error in error handler: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "error": True,
                "error_code": "CRITICAL_ERROR",
                "message": "A critical error occurred. Please contact support.",
                "details": {}
            }
        )

def log_error_context(error: Exception, context: Dict[str, Any]):
    """
    Log error with additional context.
    
    Args:
        error: Exception that occurred
        context: Additional context information
    """
    try:
        context_str = ", ".join([f"{k}={v}" for k, v in context.items()])
        logger.error(f"Error with context [{context_str}]: {error}", exc_info=True)
    except Exception as e:
        logger.error(f"Failed to log error context: {e}")

def safe_execute(func, *args, **kwargs):
    """
    Safely execute a function with error handling.
    
    Args:
        func: Function to execute
        *args: Positional arguments
        **kwargs: Keyword arguments
        
    Returns:
        Tuple of (success: bool, result: Any, error: Exception or None)
    """
    try:
        result = func(*args, **kwargs)
        return True, result, None
    except Exception as e:
        logger.error(f"Safe execution failed for {func.__name__}: {e}")
        return False, None, e

async def safe_execute_async(func, *args, **kwargs):
    """
    Safely execute an async function with error handling.
    
    Args:
        func: Async function to execute
        *args: Positional arguments
        **kwargs: Keyword arguments
        
    Returns:
        Tuple of (success: bool, result: Any, error: Exception or None)
    """
    try:
        result = await func(*args, **kwargs)
        return True, result, None
    except Exception as e:
        logger.error(f"Safe async execution failed for {func.__name__}: {e}")
        return False, None, e 