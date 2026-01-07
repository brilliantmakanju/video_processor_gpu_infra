import time
import functools
from utils.logging import log

def retry(exceptions, tries=3, delay=1, backoff=2, logger=log):
    """
    Retry decorator with exponential backoff.
    
    :param exceptions: Exception or tuple of exceptions to catch.
    :param tries: Maximum number of attempts.
    :param delay: Initial delay between attempts in seconds.
    :param backoff: Backoff multiplier (e.g., 2 will double the delay each time).
    :param logger: Logger function to use.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            mtries, mdelay = tries, delay
            while mtries > 1:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    msg = f"[RETRY] {str(e)}, Retrying in {mdelay} seconds..."
                    if logger:
                        logger(msg)
                    else:
                        print(msg)
                    time.sleep(mdelay)
                    mtries -= 1
                    mdelay *= backoff
            return func(*args, **kwargs)
        return wrapper
    return decorator
