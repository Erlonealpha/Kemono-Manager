import asyncio
from kemonobakend.api import KemonoAPI
import aiomultiprocess

class Program:
    def __init__(self):
        self.kemono_api = KemonoAPI()