from ... import configurator, hyperogger, utils
from .translator import MilkyHttpConnection

reports = utils.KeyQueue()

config: configurator.BotConfig
logger: hyperogger.Logger


def init() -> None:
    global config, logger
    config = configurator.BotConfig.get("hyper-bot")
    logger = hyperogger.Logger()
    logger.set_level(config.log_level)


class Packet:
    def __init__(self, endpoint: str, **kwargs):
        self.endpoint = endpoint
        self.paras = kwargs

    async def send_to(self, connection: MilkyHttpConnection) -> dict:
        if isinstance(connection, MilkyHttpConnection):
            return await connection.http_send(self.endpoint, self.paras)
        raise TypeError(f"Invalid connection: {connection}")
