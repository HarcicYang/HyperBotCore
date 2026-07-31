from typing import TypedDict


class OneBotJsonPacket(TypedDict):
    action: str
    params: dict
    echo: str | None


class OneBotSegReg(TypedDict):
    type: type
    args: list[str]
