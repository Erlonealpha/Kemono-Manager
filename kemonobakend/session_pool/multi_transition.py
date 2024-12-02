
from multiprocessing import Lock, Process, Queue, Value, Pipe

from .session_pool import SessionPool

class MultiProcessTransaction:
    def __init__(self, pool: SessionPool):
        h1, h2 = Pipe()
        self.raw = h1
        self.result = h2
        self._pool = pool