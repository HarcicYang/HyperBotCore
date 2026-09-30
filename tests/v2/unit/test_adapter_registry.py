import asyncio

from hyperot.v2.actions import Action, SendMessageAction, SendResult
from hyperot.v2.adapter import ActionRegistry
from hyperot.v2.common import CapabilityNotSupportedError, GroupId, MessageId, SceneType
from hyperot.v2.messages import Message, Text


class CustomAction(Action[SendResult]):
    pass


def test_action_registry_supports_extension_and_replacement():
    async def handler(_action: SendMessageAction) -> SendResult:
        return SendResult(message_id=MessageId("m1"))

    async def custom(_action: CustomAction) -> SendResult:
        return SendResult(message_id=MessageId("m2"))

    async def run() -> None:
        registry = ActionRegistry()
        registry.register(SendMessageAction, handler)
        registry.register(CustomAction, custom)
        action = SendMessageAction(
            scene_type=SceneType.GROUP,
            scene_id=GroupId("1"),
            message=Message(Text(text="x")),
        )
        result = await registry.get(SendMessageAction)(action)
        assert result.message_id == "m1"
        assert registry.supports(CustomAction)
        try:
            registry.get(Action)
        except CapabilityNotSupportedError:
            pass
        else:
            raise AssertionError("missing capability was accepted")

    asyncio.run(run())
