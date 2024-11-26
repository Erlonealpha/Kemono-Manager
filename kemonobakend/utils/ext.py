from apscheduler.schedulers.asyncio import (
    AsyncIOScheduler as _AsyncIOScheduler,
)
from kemonobakend.utils.helpers import get_running_loop

class AsyncIOScheduler(_AsyncIOScheduler):
    def start(self, paused=False, loop=None):
        if loop is None:
            loop = get_running_loop()
        self._eventloop = loop
        return super().start(paused)