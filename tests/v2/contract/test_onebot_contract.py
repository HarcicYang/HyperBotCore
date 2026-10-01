import tomllib
from pathlib import Path

from hyperot_adapter_onebot import OneBotConfig, create_adapter
from hyperot_adapter_onebot.actions import (
    ONEBOT_ENDPOINTS,
    GetForwardMessageAction,
    OneBotActions,
    SendGroupMessageAction,
)
from hyperot_adapter_onebot.segments import OneBotSegmentCodec

from hyperot.v2.adapter import ActionRegistry, validate_manifest
from hyperot.v2.messages import Message, Text

_ROOT = Path(__file__).resolve().parents[3]


def test_manifest_and_config_contract():
    adapter = create_adapter()
    validate_manifest(adapter.manifest)
    assert adapter.config_type is OneBotConfig
    config = OneBotConfig.model_validate({"connections": [{"type": "ForwardWebSocket", "url": "ws://127.0.0.1:1"}]})
    assert config.connections[0].type == "ForwardWebSocket"


def test_adapter_manifest_matches_pyproject():
    with open(_ROOT / "adapters" / "onebot" / "pyproject.toml", "rb") as file:
        pyproject = tomllib.load(file)
    adapter = create_adapter()
    entrypoints = pyproject["project"]["entry-points"]["hyperot.adapters"]

    assert pyproject["project"]["version"] == adapter.manifest.version
    assert entrypoints["onebot"] == adapter.manifest.entrypoint


def test_segment_codec_contract():
    adapter = create_adapter()
    message = Message(Text(text="hello"))
    wire = adapter.segment_codec.encode_message(message)
    restored = adapter.segment_codec.decode_message(wire)
    assert str(restored) == "hello"


class FakeTransport:
    async def call(self, action, params, timeout):
        return {"status": "ok", "retcode": 0, "data": {}}


def test_adapter_registers_all_onebot_actions():
    registry = ActionRegistry()
    builder = OneBotActions(FakeTransport(), OneBotSegmentCodec(), 30.0)
    builder.register_all(registry)
    assert len(ONEBOT_ENDPOINTS) == 34
    assert len(registry.action_types()) >= 34


def test_adapter_action_log_summaries():
    send = SendGroupMessageAction(group_id="100", message=Message(Text(text="hello")))
    assert send.log_level == "INFO"
    assert send.log_summary() == "[group] 100 send: hello"

    forward = GetForwardMessageAction(forward_id="f1")
    assert forward.log_level == "TRACE"
    assert forward.log_summary() == "fetch forward f1"
