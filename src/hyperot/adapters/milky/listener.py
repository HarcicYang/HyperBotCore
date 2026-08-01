from typing_extensions import override

from ... import configurator, events
from ...protocol import ActionsBase, BaseListener
from .actions import MilkyActions
from .packet import Packet  # noqa: F401  (re-export for tests)
from .translator import MilkyHttpConnection

config = configurator.BotConfig.get("hyper-bot")


class MilkyListener(BaseListener):
    def __init__(self):
        super().__init__()
        self.config = config

    @override
    def build_connection(self) -> MilkyHttpConnection:
        if not isinstance(self.config.connection, configurator.MilkyConnection):
            raise TypeError("Milky 协议需要 MilkyConnection 类型的连接配置")
        connection_cfg = self.config.connection
        return MilkyHttpConnection(f"ws://{connection_cfg.host}:{connection_cfg.port}", auth=connection_cfg.auth)

    @override
    def new_actions(self, connection) -> MilkyActions:
        return MilkyActions(connection)

    @override
    async def process(self, data: dict, actions: ActionsBase) -> None:
        await self.handler(events.em.new(data), actions)
