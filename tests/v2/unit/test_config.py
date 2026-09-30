import json

from pydantic import BaseModel

from hyperot.v2.config import load_raw_app_config


class AdapterConfig(BaseModel):
    host: str
    port: int


def test_load_raw_config_validates_adapter_settings(tmp_path):
    path = tmp_path / "appconfig.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "active_adapter": "onebot",
                "adapter_config": {"host": "127.0.0.1", "port": 5004},
                "runtime": {},
                "logging": {},
            }
        ),
        encoding="utf-8",
    )
    raw = load_raw_app_config(path)
    assert raw.active_adapter == "onebot"
    assert AdapterConfig.model_validate(raw.adapter_config).port == 5004
