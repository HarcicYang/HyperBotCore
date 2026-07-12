from . import configurator
from .utils import screens

from typing import Union, Callable, TYPE_CHECKING, Any
import asyncio
import sys
import os
import signal

HYPER_BOT_VERSION = "0.82.3"

# listener = None

screens.play_startup()
screens.play_info(HYPER_BOT_VERSION)

if TYPE_CHECKING:
    from . import events, listener, hyperogger

    ANY_EVENT = Union[
        events.GroupMessageEvent,
        events.PrivateMessageEvent,
        events.GroupFileUploadEvent,
        events.GroupAdminEvent,
        events.GroupMemberDecreaseEvent,
        events.GroupMemberIncreaseEvent,
        events.GroupMuteEvent,
        events.FriendAddEvent,
        events.GroupRecallEvent,
        events.FriendRecallEvent,
        events.NotifyEvent,
        events.GroupEssenceEvent,
        events.MessageReactionEvent,
        events.GroupAddInviteEvent,
        events.HyperListenerStartNotify,
        events.HyperListenerStopNotify
    ]
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

    def subscribe(
            self,
            func: Callable,
            event: Union[ANY_EVENT, list[ANY_EVENT]]
    ) -> None:
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

    async def distributor(
            self, message_data: Union["events.Event", "events.HyperNotify"], actions: LISTENER_ACTIONS
    ) -> None:
        if type(message_data) in list(self.records.keys()):
            tasks = []
            for i in self.records[type(message_data)]:
                tasks.append(asyncio.create_task(i(message_data, actions)))
            await asyncio.gather(*tasks)
        else:
            return

    async def run(self):
        from . import listener
        self.lis = listener
        self.lis.reg(self.distributor)
        if self.records:
            stop = asyncio.Event()
            loop = asyncio.get_running_loop()
            _wakeup_task = None
            if sys.platform == "win32":
                def _win32_handler(signum, frame):  # type: ignore
                    stop.set()

                signal.signal(signal.SIGINT, _win32_handler)
                try:
                    signal.signal(signal.SIGBREAK, _win32_handler)
                except AttributeError:
                    pass

                async def _win32_wakeup():
                    while 1:
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

    def restart(self) -> None:
        self.lis.stop()
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
        exit(-1)

    if True:
        from hyperot import hyperogger
        from hyperot.adapters import builtins as adp

        config = configurator.BotConfig.get("hyper-bot")
        logger = hyperogger.Logger()
        logger.set_level(config.log_level)

        match config.protocol:
            case "OneBot":
                adp.load_onebot()
            case _:
                raise NotImplementedError

    return logger
