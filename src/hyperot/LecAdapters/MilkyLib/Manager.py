from .translator import MilkyHttpConnection


class Packet:
    def __init__(self, endpoint: str, **kwargs):
        self.endpoint = endpoint
        self.paras = kwargs

    async def send_to(self, connection: MilkyHttpConnection) -> dict:
        if isinstance(connection, MilkyHttpConnection):
            return await connection.http_send(self.endpoint, self.paras)
        raise TypeError(f"Invalid connection: {connection}")
