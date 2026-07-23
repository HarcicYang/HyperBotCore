from cfgr.manager import BaseConfig


__all__ = [
    "BotConfig",
    "BotWSC",
    "BotHTTPC"
]


class BotWSC(BaseConfig):
    mode: str = "FWS"
    ob_auto_startup: bool = False
    ob_exec: str = None
    ob_startup_path: str = None
    ob_log_output: bool = False
    host: str
    port: int
    retries: int = 5
    token: str
    auth: str


class BotHTTPC(BaseConfig):
    mode: str = "HTTPC"
    ob_auto_startup: bool = False
    ob_exec: str = None
    ob_startup_path: str = None
    ob_log_output: bool = False
    host: str
    port: int
    listener_host: str
    listener_port: int
    retries: int = 5
    auth: str


class BotConfig(BaseConfig):
    protocol: str = "OneBot"
    owner: list
    black_list: list
    silents: list
    connection: BotHTTPC
    connection: BotWSC
    connection: dict
    log_level: str = "INFO"
    log_use_nf: bool = False
    uin: int
    max_workers: int
    others: dict

    def custom_post(self, **kwargs):
        if isinstance(self.connection, dict):
            if self.protocol == "OneBot":
                if self.connection["mode"] == "FWS":
                    self.connection = BotWSC(**self.connection)
                elif self.connection["mode"] == "HTTPC":
                    self.connection = BotHTTPC(**self.connection)
        else:
            raise TypeError()

        if isinstance(self.connection, dict):
            raise TypeError()
