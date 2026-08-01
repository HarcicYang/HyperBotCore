from cfgr.manager import BaseConfig
from typing_extensions import override

__all__ = ["BotConfig", "BotHTTPC", "BotWSC", "MilkyConnection"]


class BotWSC(BaseConfig):
    mode: str = "FWS"
    ob_auto_startup: bool = False
    ob_exec: str | None = None
    ob_startup_path: str | None = None
    ob_log_output: bool = False
    host: str
    port: int
    retries: int = 5
    token: str
    auth: str


class BotHTTPC(BaseConfig):
    mode: str = "HTTPC"
    ob_auto_startup: bool = False
    ob_exec: str | None = None
    ob_startup_path: str | None = None
    ob_log_output: bool = False
    host: str
    port: int
    listener_host: str
    listener_port: int
    retries: int = 5
    auth: str


class MilkyConnection(BaseConfig):
    mode: str = "Milky"
    host: str
    port: int
    retries: int = 5
    auth: str = ""


class BotConfig(BaseConfig):
    protocol: str = "OneBot"
    owner: list
    black_list: list
    silents: list
    connection: BotHTTPC | BotWSC | MilkyConnection | dict
    log_level: str = "INFO"
    log_use_nf: bool = False
    uin: int
    others: dict

    @override
    def custom_post(self, **kwargs):
        if isinstance(self.connection, dict):
            match self.protocol:
                case "OneBot":
                    if self.connection["mode"] == "FWS":
                        self.connection = BotWSC(**self.connection)
                    elif self.connection["mode"] == "HTTPC":
                        self.connection = BotHTTPC(**self.connection)
                case "Milky":
                    self.connection = MilkyConnection(**self.connection)
        else:
            raise TypeError()

        if isinstance(self.connection, dict):
            raise TypeError()
