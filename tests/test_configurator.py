import json

import pytest
from cfgr.manager import Serializers

from hyperot.configurator import BotConfig
from hyperot.utils import errors


def _load(tmp_path, protocol: str, mode: str):
    cfg = {
        "protocol": protocol,
        "owner": [],
        "black_list": [],
        "silents": [],
        "connection": {"mode": mode, "host": "127.0.0.1", "port": 1},
        "log_level": "ERROR",
        "log_use_nf": False,
        "uin": 0,
        "others": {},
    }
    path = tmp_path / "cfg.json"
    path.write_text(json.dumps(cfg), encoding="utf-8")
    return BotConfig.load_from(str(path), Serializers.JSON, f"test-{protocol}-{mode}")


def test_custom_post_unknown_mode(tmp_path):
    with pytest.raises(errors.ConfigError):
        _load(tmp_path, "OneBot", "UNKNOWN")


def test_custom_post_unknown_protocol(tmp_path):
    with pytest.raises(errors.ConfigError):
        _load(tmp_path, "Foo", "FWS")


def test_custom_post_parses_onebot_fws(tmp_path):
    cfg = _load(tmp_path, "OneBot", "FWS")
    from hyperot.configurator import BotWSC

    assert isinstance(cfg.connection, BotWSC)
    cfg.custom_post()  # 幂等：已转换后再次调用不报错


def test_custom_post_parses_onebot_httpc(tmp_path):
    cfg = _load(tmp_path, "OneBot", "HTTPC")
    from hyperot.configurator import BotHTTPC

    assert isinstance(cfg.connection, BotHTTPC)


def test_custom_post_parses_milky(tmp_path):
    cfg = _load(tmp_path, "Milky", "Milky")
    from hyperot.configurator import MilkyConnection

    assert isinstance(cfg.connection, MilkyConnection)
