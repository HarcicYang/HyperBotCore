from cfgr.manager import BaseConfig
from typing_extensions import override

from .utils.errors import ConfigError

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
        if isinstance(self.connection, (BotWSC, BotHTTPC, MilkyConnection)):
            return
        if not isinstance(self.connection, dict):
            raise TypeError(f"无效的 connection 配置：{type(self.connection).__name__}")

        match self.protocol:
            case "OneBot":
                mode = self.connection.get("mode")
                if mode == "FWS":
                    self.connection = BotWSC(**self.connection)
                elif mode == "HTTPC":
                    self.connection = BotHTTPC(**self.connection)
                else:
                    raise ConfigError(f"未知的连接模式：{mode}")
            case "Milky":
                self.connection = MilkyConnection(**self.connection)
            case _:
                raise ConfigError(f"未知的协议：{self.protocol}")

        if isinstance(self.connection, dict):
            raise ConfigError("connection 配置无法解析，请检查 protocol 与 mode 是否匹配")
