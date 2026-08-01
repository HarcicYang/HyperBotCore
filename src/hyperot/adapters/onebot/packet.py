import json
import uuid

from ... import network
from ...utils.hypetyping import OneBotJsonPacket


class Packet:
    def __init__(self, endpoint: str, **kwargs):
        self.endpoint = endpoint
        self.paras = kwargs
        self.echo = f"{endpoint}_{uuid.uuid4().hex[:8]}"

    async def send_to(self, connection: network.WebsocketConnection | network.HTTPConnection) -> None:
        if isinstance(connection, network.WebsocketConnection):
            payload: OneBotJsonPacket = {
                "action": self.endpoint,
                "params": self.paras,
                "echo": self.echo,
            }
            await connection.send(json.dumps(payload))

        elif isinstance(connection, network.HTTPConnection):
            await connection.send(self.endpoint, self.paras, self.echo)
