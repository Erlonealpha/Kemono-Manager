from asyncio import AbstractEventLoop, get_event_loop, get_running_loop
from warnings import warn
from typing import Optional

def get_running_loop(
    loop: Optional[AbstractEventLoop] = None,
) -> AbstractEventLoop:
    if loop is None:
        loop = get_event_loop()
    if not loop.is_running():
        warn(
            "The object should be created within an async function",
            DeprecationWarning,
            stacklevel=3,
        )
    return loop