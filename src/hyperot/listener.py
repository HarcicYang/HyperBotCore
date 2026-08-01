from . import configurator, events
from .adapters import registry
from .protocol import ActionsBase as Actions

config = configurator.BotConfig.get("hyper-bot")

__all__ = ["Actions", "config", "reg", "run", "stop"]


def reg(func) -> None:
    if registry.current is None:
        raise RuntimeError("适配器尚未加载，请先调用 hyperot.init()")
    registry.current.listener.reg(func)


async def run() -> None:
    if registry.current is None:
        raise RuntimeError("适配器尚未加载，请先调用 hyperot.init()")
    await registry.current.listener.run()


async def stop() -> None:
    if registry.current is None:
        raise RuntimeError("适配器尚未加载，请先调用 hyperot.init()")
    await registry.current.listener.stop()


events.init()
