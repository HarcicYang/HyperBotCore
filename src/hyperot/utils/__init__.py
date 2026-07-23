import asyncio
from typing import Any


class KeyQueue:
    def __init__(self):
        self.contents = {}

    async def put(self, key: str, obj: Any) -> None:
        if key in list(self.contents.keys()):
            return
        self.contents[key] = obj

    async def get(self, key: str) -> Any:
        while 1:
            try:
                rs = self.contents[key]
                del self.contents[key]
                return rs
            except KeyError:
                await asyncio.sleep(0.01)
                pass
