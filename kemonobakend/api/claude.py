if __name__ == '__main__':
    import sys, os
    sys.path.append(os.getcwd())

import os
from asyncio import run
from claude_api import AsyncClient
from kemonobakend.config import settings
from kemonobakend.event_loop import EventLoop, get_event_loop


async def test(event_loop: EventLoop):
    cookie = os.getenv("CLAUDE_COOKIE")
    proxy = "http://127.0.0.1:7890"
    client = AsyncClient(event_loop.get_loop(), cookie, proxy=proxy)
    client.organization_id = await client.get_organization_id()
    data = await client.list_all_conversations()
    print(data)

if __name__ == '__main__':
    event_loop = get_event_loop()
    event_loop.run_threadsafe(test(event_loop)).result()
    