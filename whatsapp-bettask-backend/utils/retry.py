"""
Retry utility for handling network failures and API retries.

Provides decorators and utilities for automatic retry logic.
"""

import asyncio
import logging
from functools import wraps
from typing import Callable, Any, Optional, List, Type
import random

from utils.logger import setup_logger

logger = setup_logger(__name__)

def with_retry(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff_factor: float = 2.0,
    jitter: bool = True,
    exceptions: Optional[List[Type[Exception]]] = None
):
    """
    Decorator for automatic retry logic with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts
        delay: Initial delay between retries in seconds
        backoff_factor: Multiplier for delay on each retry
        jitter: Add random jitter to prevent thundering herd
        exceptions: List of exception types to retry on (default: all)
    
    Returns:
        Decorated function with retry logic
    """
    if exceptions is None:
        exceptions = [Exception]
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    
                    # Check if this exception type should be retried
                    if not any(isinstance(e, exc_type) for exc_type in exceptions):
                        logger.error(f"Non-retryable exception in {func.__name__}: {e}")
                        raise
                    
                    # Don't retry on the last attempt
                    if attempt == max_retries:
                        break
                    
                    # Calculate delay with jitter
                    actual_delay = current_delay
                    if jitter:
                        actual_delay += random.uniform(0, current_delay * 0.1)
                    
                    logger.warning(
                        f"Attempt {attempt + 1}/{max_retries + 1} failed for {func.__name__}: {e}. "
                        f"Retrying in {actual_delay:.2f} seconds..."
                    )
                    
                    await asyncio.sleep(actual_delay)
                    current_delay *= backoff_factor
            
            # All retries exhausted
            logger.error(f"All {max_retries + 1} attempts failed for {func.__name__}")
            raise last_exception
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    
                    # Check if this exception type should be retried
                    if not any(isinstance(e, exc_type) for exc_type in exceptions):
                        logger.error(f"Non-retryable exception in {func.__name__}: {e}")
                        raise
                    
                    # Don't retry on the last attempt
                    if attempt == max_retries:
                        break
                    
                    # Calculate delay with jitter
                    actual_delay = current_delay
                    if jitter:
                        actual_delay += random.uniform(0, current_delay * 0.1)
                    
                    logger.warning(
                        f"Attempt {attempt + 1}/{max_retries + 1} failed for {func.__name__}: {e}. "
                        f"Retrying in {actual_delay:.2f} seconds..."
                    )
                    
                    import time
                    time.sleep(actual_delay)
                    current_delay *= backoff_factor
            
            # All retries exhausted
            logger.error(f"All {max_retries + 1} attempts failed for {func.__name__}")
            raise last_exception
        
        # Return appropriate wrapper based on whether function is async
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator

class RetryableError(Exception):
    """Exception that indicates operation should be retried."""
    pass

class NonRetryableError(Exception):
    """Exception that indicates operation should NOT be retried."""
    pass

async def retry_async_operation(
    operation: Callable,
    max_retries: int = 3,
    delay: float = 1.0,
    backoff_factor: float = 2.0,
    *args,
    **kwargs
) -> Any:
    """
    Retry an async operation with exponential backoff.
    
    Args:
        operation: Async function to retry
        max_retries: Maximum number of retry attempts
        delay: Initial delay between retries
        backoff_factor: Multiplier for delay on each retry
        *args: Arguments to pass to operation
        **kwargs: Keyword arguments to pass to operation
    
    Returns:
        Result of the operation
    
    Raises:
        Last exception if all retries fail
    """
    last_exception = None
    current_delay = delay
    
    for attempt in range(max_retries + 1):
        try:
            return await operation(*args, **kwargs)
        except NonRetryableError:
            # Don't retry these exceptions
            raise
        except Exception as e:
            last_exception = e
            
            if attempt == max_retries:
                break
            
            logger.warning(
                f"Attempt {attempt + 1}/{max_retries + 1} failed: {e}. "
                f"Retrying in {current_delay:.2f} seconds..."
            )
            
            await asyncio.sleep(current_delay)
            current_delay *= backoff_factor
    
    logger.error(f"All {max_retries + 1} attempts failed")
    raise last_exception

def is_network_error(exception: Exception) -> bool:
    """
    Check if an exception is a network-related error that should be retried.
    
    Args:
        exception: Exception to check
        
    Returns:
        bool: True if it's a retryable network error
    """
    import aiohttp
    
    # Common network-related exceptions
    network_exceptions = (
        ConnectionError,
        TimeoutError,
        OSError,
    )
    
    # aiohttp specific exceptions
    aiohttp_exceptions = (
        aiohttp.ClientError,
        aiohttp.ServerTimeoutError,
        aiohttp.ClientConnectorError,
        aiohttp.ServerConnectionError,
    )
    
    return isinstance(exception, network_exceptions + aiohttp_exceptions)

def is_rate_limit_error(exception: Exception) -> bool:
    """
    Check if an exception is a rate limit error.
    
    Args:
        exception: Exception to check
        
    Returns:
        bool: True if it's a rate limit error
    """
    if hasattr(exception, 'status') or hasattr(exception, 'status_code'):
        status = getattr(exception, 'status', None) or getattr(exception, 'status_code', None)
        return status in [429, 503]  # Too Many Requests, Service Unavailable
    
    return False

# Predefined retry decorators for common scenarios
network_retry = with_retry(
    max_retries=3,
    delay=1.0,
    backoff_factor=2.0,
    exceptions=[ConnectionError, TimeoutError, OSError]
)

api_retry = with_retry(
    max_retries=5,
    delay=0.5,
    backoff_factor=1.5,
    jitter=True
)

database_retry = with_retry(
    max_retries=3,
    delay=0.1,
    backoff_factor=2.0,
    jitter=False
) 