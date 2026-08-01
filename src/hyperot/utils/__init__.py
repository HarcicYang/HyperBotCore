import asyncio
from typing import Any


class KeyQueue:
    def __init__(self):
        self.contents: dict[str, Any] = {}
        self._cond = asyncio.Condition()

    async def put(self, key: str, obj: Any) -> None:
        async with self._cond:
            if key in list(self.contents.keys()):
                return
            self.contents[key] = obj
            self._cond.notify_all()

    async def get(self, key: str) -> Any:
        async with self._cond:
            while key not in list(self.contents.keys()):
                await self._cond.wait()
            return self.contents.pop(key)
