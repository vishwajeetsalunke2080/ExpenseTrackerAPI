"""Database retry utilities for handling transient failures."""
import asyncio
import logging
from typing import TypeVar, Callable, Any
from functools import wraps
from sqlalchemy.exc import (
    OperationalError,
    DBAPIError,
    TimeoutError as SQLAlchemyTimeoutError,
    DisconnectionError
)

logger = logging.getLogger(__name__)

T = TypeVar('T')


def is_transient_error(error: Exception) -> bool:
    """Check if an error is transient and should be retried.
    
    Args:
        error: The exception to check
        
    Returns:
        bool: True if the error is transient and can be retried
    """
    # Check for specific transient error patterns
    error_msg = str(error).lower()
    
    transient_patterns = [
        'connection',
        'timeout',
        'pool',
        'network',
        'temporary',
        'deadlock',
        'lock',
        'busy',
        'unavailable',
        'terminating',
        'closed',
        'broken pipe',
        'connection reset',
    ]
    
    # Check if it's a known transient SQLAlchemy error
    if isinstance(error, (
        OperationalError,
        DBAPIError,
        SQLAlchemyTimeoutError,
        DisconnectionError
    )):
        return True
    
    # Check error message for transient patterns
    return any(pattern in error_msg for pattern in transient_patterns)


def retry_on_transient_error(
    max_retries: int = 3,
    initial_delay: float = 0.1,
    backoff_factor: float = 2.0,
    max_delay: float = 5.0
):
    """Decorator to retry database operations on transient errors.
    
    Uses exponential backoff with jitter for retries.
    
    Args:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay between retries in seconds
        backoff_factor: Multiplier for delay after each retry
        max_delay: Maximum delay between retries in seconds
        
    Usage:
        @retry_on_transient_error(max_retries=3)
        async def query_database(db: AsyncSession):
            result = await db.execute(select(User))
            return result.scalars().all()
    """
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            last_error = None
            delay = initial_delay
            
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    
                    # Don't retry if it's not a transient error
                    if not is_transient_error(e):
                        logger.error(f"Non-transient error in {func.__name__}: {str(e)}")
                        raise
                    
                    # Don't retry if we've exhausted attempts
                    if attempt >= max_retries:
                        logger.error(
                            f"Max retries ({max_retries}) exceeded for {func.__name__}: {str(e)}"
                        )
                        raise
                    
                    # Log retry attempt
                    logger.warning(
                        f"Transient error in {func.__name__} (attempt {attempt + 1}/{max_retries}): {str(e)}. "
                        f"Retrying in {delay:.2f}s..."
                    )
                    
                    # Wait before retrying with exponential backoff
                    await asyncio.sleep(delay)
                    
                    # Increase delay for next retry (exponential backoff)
                    delay = min(delay * backoff_factor, max_delay)
            
            # This should never be reached, but just in case
            raise last_error
        
        return wrapper
    return decorator


async def execute_with_retry(
    func: Callable[..., T],
    *args,
    max_retries: int = 3,
    initial_delay: float = 0.1,
    **kwargs
) -> T:
    """Execute a database operation with retry logic.
    
    Alternative to the decorator for one-off operations.
    
    Args:
        func: The async function to execute
        *args: Positional arguments for the function
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay between retries in seconds
        **kwargs: Keyword arguments for the function
        
    Returns:
        The result of the function
        
    Usage:
        result = await execute_with_retry(
            db.execute,
            select(User).where(User.id == user_id),
            max_retries=3
        )
    """
    last_error = None
    delay = initial_delay
    backoff_factor = 2.0
    max_delay = 5.0
    
    for attempt in range(max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            last_error = e
            
            if not is_transient_error(e):
                raise
            
            if attempt >= max_retries:
                logger.error(f"Max retries ({max_retries}) exceeded: {str(e)}")
                raise
            
            logger.warning(
                f"Transient error (attempt {attempt + 1}/{max_retries}): {str(e)}. "
                f"Retrying in {delay:.2f}s..."
            )
            
            await asyncio.sleep(delay)
            delay = min(delay * backoff_factor, max_delay)
    
    raise last_error
