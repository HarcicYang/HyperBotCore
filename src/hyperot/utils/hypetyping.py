from typing import Optional, TypedDict


class OneBotJsonPacket(TypedDict):
    action: str
    params: dict
    echo: Optional[str]


class OneBotSegReg(TypedDict):
    type: type
    args: list[str]
