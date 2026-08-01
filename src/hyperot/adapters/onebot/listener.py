from typing_extensions import override

from ... import configurator, events, network
from ...protocol import ActionsBase, BaseListener
from ...utils import KeyQueue
from .actions import OneBotActions
from .packet import Packet  # noqa: F401  (re-export for tests)

config = configurator.BotConfig.get("hyper-bot")
reports = KeyQueue()


class OneBotListener(BaseListener):
    def __init__(self):
        super().__init__()
        self.config = config

    @override
    def build_connection(self) -> network.WebsocketConnection | network.HTTPConnection:
        connection_cfg = self.config.connection
        if isinstance(connection_cfg, configurator.BotWSC):
            return network.WebsocketConnection(f"ws://{connection_cfg.host}:{connection_cfg.port}/")
        if isinstance(connection_cfg, configurator.BotHTTPC):
            return network.HTTPConnection(
                url=f"http://{connection_cfg.host}:{connection_cfg.port}",
                listener_url=f"http://{connection_cfg.listener_host}:{connection_cfg.listener_port}",
            )
        raise TypeError("OneBot 协议需要 BotWSC 或 BotHTTPC 类型的连接配置")

    @override
    def new_actions(self, connection) -> OneBotActions:
        return OneBotActions(connection)

    @override
    async def process(self, data: dict, actions: ActionsBase) -> None:
        if data.get("echo") is not None:
            await reports.put(data.get("echo"), data)
        elif data.get("post_type") == "meta_event" or data.get("user_id") == data.get("self_id"):
            pass
        else:
            await self.handler(events.em.new(data), actions)
