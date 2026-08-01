from collections.abc import Callable
from typing import Any, Generic, Self, TypeVar

from . import configurator, segments
from .adapters import registry
from .utils.typextensions import ObjectedJson

config = configurator.BotConfig.get("hyper-bot")
T = TypeVar("T")


class MessageBuilder:
    def __init__(self):
        self.sgs = []

    def __getattr__(self, item):
        if item == "build":

            def build() -> Message:
                return Message(*self.sgs)

            return build

        elif item in segments.message_types:

            def wrapper(*args, **kwargs):
                self.sgs.append(segments.message_types[item]["type"](*args, **kwargs))
                return self

            return wrapper
        else:
            return None


class Message:
    builder = MessageBuilder()

    def __init__(self, *args):
        if len(args) == 1 and isinstance(args[0], list):
            contents = args[0]
        elif len(args) >= 1:
            contents = list(args)
        else:
            contents = []
        self.contents = contents

    def add(self, content) -> None:
        self.contents.append(content)

    async def get(self) -> list:
        return self.get_sync()

    def get_sync(self) -> list:
        ret = []
        for i in self.contents:
            ret.append(i.to_json())
        return ret

    def __len__(self) -> int:
        return len(self.contents)

    def __getitem__(self, index: int):
        return self.contents[index]

    def __setitem__(self, index: int, content) -> None:
        self.contents[index] = content

    def __delitem__(self, index: int) -> None:
        del self.contents[index]

    def __iter__(self):
        yield from self.contents

    def __str__(self) -> str:
        return "".join([str(content) for content in self.contents])

    def __repr__(self) -> str:
        return str(self.contents)

    def __add__(self, new):
        self.contents += new.contents
        return self

    def __iadd__(self, new):
        self.contents += new.contents
        return self


class Ret(Generic[T]):
    def __init__(self, json_data: dict, serializer: Callable[[Any], T] = lambda x: x):  # type: ignore[misc]
        self.raw = json_data.copy()
        self.status = json_data.get("status")
        self.ret_code = json_data.get("retcode")
        self.data: T = serializer(json_data.get("data"))
        self.echo = json_data.get("echo")

    @classmethod
    async def fetch(cls, echo: str, serializer=ObjectedJson) -> Self:
        if registry.current is None:
            raise RuntimeError("适配器尚未加载，请先调用 hyperot.init()")
        return cls(await registry.current.reports.get(echo), serializer)
