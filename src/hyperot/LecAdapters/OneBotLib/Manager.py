from ... import configurator, hyperogger, network, utils
from ...utils.hypetyping import OneBotJsonPacket

from typing import Union
import random
import json

reports = utils.KeyQueue()

config: configurator.BotConfig
logger: hyperogger.Logger


def init() -> None:
    global config, logger
    config = configurator.BotConfig.get("hyper-bot")
    logger = hyperogger.Logger()
    logger.set_level(config.log_level)


servicing = []


class Packet:
    def __init__(self, endpoint: str, **kwargs):
        self.endpoint = endpoint
        self.paras = kwargs
        self.echo = f"{endpoint}_{random.randint(1000, 9999)}"

    async def send_to(self, connection: Union[network.WebsocketConnection, network.HTTPConnection]) -> None:
        if isinstance(connection, network.WebsocketConnection):
            payload: OneBotJsonPacket = {
                "action": self.endpoint,
                "params": self.paras,
                "echo": self.echo,
            }
            await connection.send(json.dumps(payload))

        elif isinstance(connection, network.HTTPConnection):
            payload = self.paras
            await connection.send(self.endpoint, payload, self.echo)



