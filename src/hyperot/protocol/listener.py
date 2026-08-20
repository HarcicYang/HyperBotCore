import asyncio
import json
import sys
import time
from collections.abc import Callable
from typing import Any

from websockets.exceptions import ConnectionClosed

from .. import configurator, hyperogger
from ..events import HyperListenerStartNotify, HyperListenerStopNotify, HyperNotify
from ..utils import errors
from .actions import ActionsBase

__all__ = ["BaseListener"]

logger = hyperogger.Logger.create("hyperot.protocol.listener", configurator.BotConfig.get("hyper-bot").log_level)


async def tester(message_data: Any, actions: ActionsBase) -> None: ...


class BaseListener:
    """协议无关的监听器骨架。

    子类需实现 hooks：`build_connection`、`new_actions`、`process`，
    并在 `__init__` 中设置 `config`（用于读取重试次数等连接配置）。
    """

    handler: Callable
    connection: Any
    config: configurator.BotConfig

    def __init__(self):
        self.handler = tester
        self.connection = None

    def reg(self, func: Callable) -> None:
        self.handler = func

    def build_connection(self) -> Any: ...

    def new_actions(self, connection: Any) -> ActionsBase: ...

    async def process(self, data: dict, actions: ActionsBase) -> None: ...

    async def _handler(self, data: dict | HyperNotify | None, actions: ActionsBase) -> None:
        if data is None:
            return
        try:
            if isinstance(data, dict):
                await self.process(data, actions)
            else:
                await self.handler(data, actions)
        except Exception:
            logger.exception("处理事件时发生异常")

    async def run(self) -> None:
        try:
            if self.handler is tester:
                raise errors.ListenerNotRegisteredError("No handler registered")
            connection = self.build_connection()
            self.connection = connection
            connection_cfg = self.config.connection
            assert isinstance(
                connection_cfg, (configurator.BotWSC, configurator.BotHTTPC, configurator.MilkyConnection)
            )
            retries = connection_cfg.retries
            retried = 0

            while True:
                try:
                    await connection.connect()
                except (ConnectionRefusedError, TimeoutError, OSError):
                    if retried >= retries:
                        logger.critical(f"重试次数达到最大值({retries})，退出")
                        break

                    logger.warning(f"连接建立失败，3秒后重试({retried}/{retries})")
                    retried += 1
                    await asyncio.sleep(3)
                    continue
                retried = 0
                logger.info(f"成功在 {connection.url} 建立连接")
                actions = self.new_actions(connection)
                start_data = HyperListenerStartNotify(
                    time_now=int(time.time()), notify_type="listener_start", connection=connection
                )
                asyncio.create_task(self._handler(start_data, actions))
                while True:
                    try:
                        data = await connection.recv()
                    except (ConnectionClosed, ConnectionResetError):
                        logger.error("连接断开")
                        break
                    except json.decoder.JSONDecodeError:
                        logger.error("收到错误的JSON内容")
                        continue
                    logger.trace(str(data))
                    if data is not None:
                        asyncio.create_task(self._handler(data, actions))
        except asyncio.CancelledError:
            logger.warning("正在退出(Ctrl+C)")
            try:
                if self.connection is not None:
                    await self.connection.close()
            except Exception:
                logger.exception("关闭连接失败")
            sys.exit()

    async def stop(self) -> None:
        try:
            if self.connection is not None:
                await self._handler(
                    HyperListenerStopNotify(time_now=int(time.time()), notify_type="listener_stop"),
                    self.new_actions(self.connection),
                )
                await self.connection.close()
        except Exception:
            logger.exception("停止监听器时关闭连接失败")
        logger.log("停止运行监听器", level=hyperogger.levels.WARNING)
