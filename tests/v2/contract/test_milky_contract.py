import tomllib
from pathlib import Path

from hyperot_adapter_milky import MilkyConfig, create_adapter
from hyperot_adapter_milky.actions import (
    MILKY_ENDPOINTS,
    GetForwardMessageAction,
    MilkyActions,
    SendGroupMessageAction,
)
from hyperot_adapter_milky.segments import MilkySegmentCodec

from hyperot.v2.adapter import ActionRegistry, validate_manifest
from hyperot.v2.messages import Message, Text

_ROOT = Path(__file__).resolve().parents[3]


def test_manifest_and_config_contract():
    adapter = create_adapter()
    validate_manifest(adapter.manifest)
    assert adapter.config_type is MilkyConfig
    config = MilkyConfig.model_validate({"connections": [{"type": "WebSocket", "url": "ws://127.0.0.1:1"}]})
    assert config.connections[0].type == "WebSocket"


def test_adapter_manifest_matches_pyproject():
    with open(_ROOT / "adapters" / "milky" / "pyproject.toml", "rb") as file:
        pyproject = tomllib.load(file)
    adapter = create_adapter()
    entrypoints = pyproject["project"]["entry-points"]["hyperot.adapters"]

    assert pyproject["project"]["version"] == adapter.manifest.version
    assert entrypoints["milky"] == adapter.manifest.entrypoint


def test_segment_codec_contract():
    adapter = create_adapter()
    message = Message(Text(text="hello"))
    wire = adapter.segment_codec.encode_message(message)
    restored = adapter.segment_codec.decode_message(wire)
    assert str(restored) == "hello"


class FakeTransport:
    async def call(self, action, params, timeout):
        return {"status": "ok", "retcode": 0, "data": {}}


def test_adapter_registers_all_milky_actions():
    registry = ActionRegistry()
    builder = MilkyActions(FakeTransport(), MilkySegmentCodec(), 30.0)
    builder.register_all(registry)
    assert len(registry.action_types()) >= len(MILKY_ENDPOINTS)
    assert "get_impl_info" in MILKY_ENDPOINTS


def test_adapter_action_log_summaries():
    send = SendGroupMessageAction(group_id="100", message=Message(Text(text="hello")))
    assert send.log_level == "INFO"
    assert send.log_summary() == "[group] 100 send: hello"

    forward = GetForwardMessageAction(forward_id="f1")
    assert forward.log_level == "TRACE"
    assert forward.log_summary() == "fetch forward f1"
