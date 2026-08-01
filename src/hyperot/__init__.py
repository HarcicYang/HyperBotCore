import asyncio
import os
import signal
import sys
from collections.abc import Callable
from importlib.metadata import PackageNotFoundError, version
from typing import TYPE_CHECKING, Any

from . import configurator
from .utils import screens

try:
    __version__ = version("hyper-bot")
except PackageNotFoundError:
    __version__ = "unknown"

HYPER_BOT_VERSION = __version__

# listener = None

screens.play_startup()
screens.play_info(HYPER_BOT_VERSION)

if TYPE_CHECKING:
    from . import events, hyperogger, listener

    ANY_EVENT = (
        events.GroupMessageEvent
        | events.PrivateMessageEvent
        | events.GroupFileUploadEvent
        | events.GroupAdminEvent
        | events.GroupMemberDecreaseEvent
        | events.GroupMemberIncreaseEvent
        | events.GroupMuteEvent
        | events.FriendAddEvent
        | events.GroupRecallEvent
        | events.FriendRecallEvent
        | events.NotifyEvent
        | events.GroupEssenceEvent
        | events.MessageReactionEvent
        | events.GroupAddInviteEvent
        | events.HyperListenerStartNotify
        | events.HyperListenerStopNotify
    )
    LISTENER_ACTIONS = listener.Actions
    LOGGER = hyperogger.Logger
else:
    ANY_EVENT = Any
    LISTENER_ACTIONS = Any
    LOGGER = Any


class Client:
    def __init__(self):
        self.records = {}
        self.lis = None

    def subscribe(self, func: Callable, event: ANY_EVENT | list[ANY_EVENT]) -> None:
        if isinstance(event, list):
            for e in event:
                self._subscribe(func, e)
        else:
            self._subscribe(func, event)

    def _subscribe(self, func: Callable, event: ANY_EVENT) -> None:
        if not self.records.get(event):
            self.records[event] = [func]
        else:
            self.records[event].append(func)

    async def distributor(self, message_data: "events.Event | events.HyperNotify", actions: LISTENER_ACTIONS) -> None:
        matches = [(cls, handlers) for cls, handlers in self.records.items() if isinstance(message_data, cls)]
        if not matches:
            return
        # 最具体（MRO 最深）的订阅优先，避免父类订阅抢占子类事件
        _cls, handlers = max(matches, key=lambda m: len(m[0].__mro__))
        tasks = [asyncio.create_task(h(message_data, actions)) for h in handlers]
        await asyncio.gather(*tasks)

    async def run(self):
        from . import hyperogger, listener

        if not self.records:
            (hyperogger.Logger.fetch("hyperot") or hyperogger.Logger()).warning("未订阅任何事件类型，监听器将立即返回")
        self.lis = listener
        self.lis.reg(self.distributor)
        if self.records:
            stop = asyncio.Event()
            loop = asyncio.get_running_loop()
            _wakeup_task = None
            if sys.platform == "win32":

                def _win32_handler(_signum, _frame):
                    stop.set()

                signal.signal(signal.SIGINT, _win32_handler)
                try:
                    signal.signal(signal.SIGBREAK, _win32_handler)
                except AttributeError:
                    pass

                async def _win32_wakeup():
                    while True:
                        await asyncio.sleep(0.1)

                _wakeup_task = asyncio.create_task(_win32_wakeup())
            else:
                for i in (signal.SIGINT, signal.SIGTERM):
                    loop.add_signal_handler(i, stop.set)  # type: ignore
            task = asyncio.create_task(self.lis.run())
            await stop.wait()
            if _wakeup_task:
                _wakeup_task.cancel()
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    async def restart(self) -> None:
        if self.lis:
            await self.lis.stop()
        os.execv(sys.executable, [sys.executable] + sys.argv)
        # os._exit(1)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


def init(cfg_file: str = "config.json") -> "hyperogger.Logger":
    from cfgr.manager import Serializers

    try:
        configurator.BotConfig.load_from(cfg_file, Serializers.JSON, "hyper-bot")
    except FileNotFoundError:
        configurator.BotConfig.create_and_write(cfg_file, Serializers.JSON)
        print("没有找到配置文件，已自动创建，请填写后重启")
        sys.exit(-1)

    from hyperot import hyperogger
    from hyperot.adapters import registry

    config = configurator.BotConfig.get("hyper-bot")
    logger = hyperogger.Logger.create("hyperot", config.log_level)

    registry.load(config.protocol)

    return logger
