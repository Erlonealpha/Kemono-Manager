import asyncio
from typing import Optional, Awaitable, Callable, Any

def pre_task(
        task: Awaitable, 
        start: bool = True,
        semaphore: Optional[asyncio.Semaphore] = None,
        callback: Optional[Callable[[], Any]] = None
    ):
    def wrap_task(task):
        async def wrapped():
            async def callback_call(callback, result=None):
                if asyncio.iscoroutinefunction(callback):
                    await callback(result)
                elif asyncio.iscoroutine(callback):
                    await callback
                else:
                    callback(result)
            try:
                async with (semaphore or asyncio.Semaphore(1)):
                    result = await task
                    if callback is not None:
                        await callback_call(callback, result)
                    return result
            except asyncio.CancelledError:
                pass
            except Exception as e:
                if callback is not None:
                    await callback_call(callback, e)
        return wrapped()
    if callback is not None or semaphore is not None:
        task = wrap_task(task)
    if start:
        return asyncio.create_task(task)
    return task

def pre_gather_tasks(
        tasks: list[Awaitable], 
        start: bool = True, 
        semaphore: Optional[asyncio.Semaphore] = None, 
        callback: Optional[Callable[[], Any]] = None
    ):
    
    return [
        pre_task(task, start=start, semaphore=semaphore, callback=callback)
        for task in tasks
    ]