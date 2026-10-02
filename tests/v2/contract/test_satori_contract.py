import tomllib
from pathlib import Path

from hyperot_adapter_satori import SatoriConfig, create_adapter
from hyperot_adapter_satori.actions import SATORI_ENDPOINTS, SatoriActions, SatoriMessageListAction
from hyperot_adapter_satori.segments import SatoriSegmentCodec

from hyperot.v2.adapter import ActionRegistry, validate_manifest
from hyperot.v2.messages import Message, Text

_ROOT = Path(__file__).resolve().parents[3]


def test_manifest_and_config_contract():
    adapter = create_adapter()
    validate_manifest(adapter.manifest)
    assert adapter.config_type is SatoriConfig
    config = SatoriConfig.model_validate({"connections": [{"type": "WebSocket", "url": "ws://127.0.0.1:5140"}]})
    assert config.connections[0].type == "WebSocket"
    assert config.connections[0].event_path == "/v1/events"


def test_adapter_manifest_matches_pyproject():
    with open(_ROOT / "adapters" / "satori" / "pyproject.toml", "rb") as file:
        pyproject = tomllib.load(file)
    adapter = create_adapter()
    entrypoints = pyproject["project"]["entry-points"]["hyperot.adapters"]

    assert pyproject["project"]["version"] == adapter.manifest.version
    assert entrypoints["satori"] == adapter.manifest.entrypoint


def test_segment_codec_contract():
    adapter = create_adapter()
    message = Message(Text(text="hello"))
    wire = adapter.segment_codec.encode_message(message)
    restored = adapter.segment_codec.decode_message(wire)
    assert str(restored) == "hello"


class FakeTransport:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def resolve_identity(self) -> tuple[str, str]:
        return "qq", "10000"

    def logins(self) -> list[dict]:
        return []

    def login_status(self, platform: str, user_id: str) -> int | None:
        return 1

    def proxy_urls(self) -> list[str]:
        return []

    def proxy_url(self, url: str) -> str:
        return f"http://127.0.0.1:5140/proxy/{url}"

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    async def receive(self) -> dict:
        return {}

    async def call(self, route: str, params: dict, timeout: float):
        self.calls.append((route, params))
        return {}

    async def upload(self, files, timeout: float) -> dict[str, str]:
        return {name: f"http://127.0.0.1:5140/{name}" for name, *_ in files}


def test_adapter_registers_all_satori_routes():
    transport = FakeTransport()
    registry = ActionRegistry()
    SatoriActions(transport, SatoriSegmentCodec(), 30.0).register_all(registry)
    assert len(registry.action_types()) >= len(SATORI_ENDPOINTS)
    assert "message.create" in SATORI_ENDPOINTS
    assert "login.get" in SATORI_ENDPOINTS


def test_adapter_action_log_summaries():
    listing = SatoriMessageListAction(channel_id="100", limit=20)
    assert listing.log_level == "TRACE"
    assert listing.log_summary() == "channel 100 message list"
