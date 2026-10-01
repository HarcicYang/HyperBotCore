import asyncio
from typing import Any

from hyperot_adapter_milky import create_adapter
from hyperot_adapter_milky.actions import MilkyActions
from hyperot_adapter_milky.events import MilkyMessageReceivedEvent

from hyperot.v2.actions import ApproveGroupRequestAction, DownloadFileAction, FileUrl, GetFileInfoAction
from hyperot.v2.adapter import ActionRegistry

GROUP_FILE_MESSAGE = {
    "time": 1700000000,
    "self_id": 10000,
    "event_type": "message_receive",
    "data": {
        "message_scene": "group",
        "peer_id": 12345,
        "message_seq": 1,
        "sender_id": 10001,
        "time": 1700000001,
        "segments": [
            {
                "type": "file",
                "data": {"file_id": "f1", "file_name": "a.zip", "file_size": 10, "file_hash": None},
            }
        ],
    },
}

GROUP_JOIN_REQUEST = {
    "time": 1700000000,
    "self_id": 10000,
    "event_type": "group_join_request",
    "data": {
        "group_id": 12345,
        "notification_seq": 9,
        "is_filtered": True,
        "initiator_id": 10001,
        "comment": "hi",
    },
}


class FakeTransport:
    def __init__(self, payloads: list[dict], data: dict[str, Any]) -> None:
        self.payloads = list(payloads)
        self.data = data
        self.calls: list[tuple[str, dict]] = []

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    async def receive(self) -> dict:
        if not self.payloads:
            await asyncio.Event().wait()
        return self.payloads.pop(0)

    async def call(self, action: str, params: dict, timeout: float) -> dict:
        self.calls.append((action, params))
        return {"status": "ok", "retcode": 0, "data": self.data}


def _started_adapter(payloads: list[dict], data: dict[str, Any]) -> tuple[Any, FakeTransport]:
    adapter = create_adapter()
    transport = FakeTransport(payloads, data)
    actions = ActionRegistry()
    MilkyActions(
        transport,
        adapter.segment_codec,
        30.0,
        file_context_lookup=adapter._file_context_lookup,
        request_context_lookup=adapter._request_context_lookup,
    ).register_all(actions)
    adapter.actions = actions
    adapter._transports = [transport]
    adapter._action_transport = transport
    adapter._running = True
    return adapter, transport


def test_received_file_can_be_downloaded_without_extra_calls():
    async def run() -> None:
        adapter, transport = _started_adapter([GROUP_FILE_MESSAGE], {"download_url": "http://x/a.zip"})
        event = await asyncio.wait_for(adapter.receive(), timeout=5)
        assert isinstance(event, MilkyMessageReceivedEvent)

        url = await adapter.execute(DownloadFileAction(file_id="f1"))
        assert isinstance(url, FileUrl)
        assert url.url == "http://x/a.zip"
        assert transport.calls == [("get_group_file_download_url", {"group_id": 12345, "file_id": "f1"})]

    asyncio.run(run())


def test_file_info_uses_the_remembered_group():
    async def run() -> None:
        data = {"files": [{"file_id": "f1", "file_name": "a.zip"}]}
        adapter, transport = _started_adapter([GROUP_FILE_MESSAGE], data)
        await asyncio.wait_for(adapter.receive(), timeout=5)

        reference = await adapter.execute(GetFileInfoAction(file_id="f1"))
        assert reference.file_id == "f1"
        assert reference.name == "a.zip"
        assert transport.calls == [("get_group_files", {"group_id": 12345, "parent_folder_id": "/"})]

    asyncio.run(run())


def test_group_request_keeps_its_notification_type():
    async def run() -> None:
        adapter, transport = _started_adapter([GROUP_JOIN_REQUEST], {})
        await asyncio.wait_for(adapter.receive(), timeout=5)

        await adapter.execute(ApproveGroupRequestAction(request_id="group_request:12345:9"))
        assert transport.calls == [
            (
                "accept_group_request",
                {
                    "notification_seq": 9,
                    "notification_type": "join_request",
                    "group_id": 12345,
                    "is_filtered": True,
                },
            )
        ]

    asyncio.run(run())
