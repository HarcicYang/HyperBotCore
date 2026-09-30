from typing import Protocol, TypeVar

from ..actions import Action

ResultT = TypeVar("ResultT")


class APIContext(Protocol):
    @property
    def running(self) -> bool: ...

    async def execute(self, action: Action[ResultT]) -> ResultT: ...
