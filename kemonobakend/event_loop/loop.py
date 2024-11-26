from threading import Thread
from concurrent.futures import Future
from asyncio import AbstractEventLoop, Task, new_event_loop, run_coroutine_threadsafe

from typing import Union, TypeVar, Coroutine, Callable, Any

_T = TypeVar('_T')

class EventLoop:
    _running = False
    def __init__(self, start=True):
        self.loop = new_event_loop()
        self.thread = Thread(target=self._run_forever)
        if start:
            self.start()
    
    def _run_forever(self):
        self.loop.run_forever()
    
    def get_loop(self) -> AbstractEventLoop:
        return self.loop

    def start(self) -> None:
        if self._running:
            return
        self.thread.start()
        self._running = True

    def stop(self) -> None:
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join()
        self._running = False
    
    def run_in_executor(self, func: Callable[..., _T], *args):
        return self.loop.run_in_executor(None, func, *args)
    
    def run_until_complete(self, future: Future[_T]) -> _T:
        return self.loop.run_until_complete(future)

    def run_threadsafe(
            self, 
            coroutine: Coroutine[None, None, _T], 
            callback: Callable[[Union[_T, Exception]], Any]=None
        ) -> Future[_T]:
        def wrapper(future: Future):
            try:
                result = future.result()
                if callback:
                    callback(result)
            except Exception as e:
                if callback:
                    callback(e)
        future = run_coroutine_threadsafe(coroutine, self.loop)
        future.add_done_callback(wrapper)
        return future

    def create_task(self, coroutine: Coroutine[None, None, Any]) -> Task:
        return self.loop.create_task(coroutine)

    def call_later(self, delay: float, callback: Callable[..., Any], *args, context=None):
        return self.loop.call_later(delay, callback, *args, context=context)

    def __del__(self):
        if self._running:
            self.stop()
    
    def __enter__(self) -> 'EventLoop':
        if not self._running:
            self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.stop()


g_event_loop_dict = {}
def get_event_loop(name: str = 'default') -> EventLoop:
    if name not in g_event_loop_dict:
        g_event_loop_dict[name] = EventLoop()
    return g_event_loop_dict[name]