import asyncio
import time

import pytest
from hyperot_adapter_onebot import OneBotConfig, create_adapter

from hyperot.v2 import Client, Message, Text

from .conftest import EulerLive

pytestmark = pytest.mark.euler_live


def test_euler_safe_live_roundtrip(euler_live: EulerLive) -> None:
    async def run() -> None:
        adapter = create_adapter()
        config = OneBotConfig.model_validate(
            {"connections": [{"type": "ForwardWebSocket", "url": euler_live.url}], "action_timeout": 30}
        )
        client = Client(adapter, config)
        await client.start()
        try:
            deadline = time.monotonic() + 30
            while True:
                try:
                    profile = await client.api.bot.profile()
                    break
                except Exception:
                    if time.monotonic() >= deadline:
                        raise
                    await asyncio.sleep(0.5)
            assert profile.display_name
            version = await client.api.bot.version()
            assert version.protocol_version

            group = await client.api.group(str(euler_live.group_id)).profile()
            assert str(group.group_id) == str(euler_live.group_id)

            user = await client.api.user(str(euler_live.user_id)).profile()
            assert str(user.user_id) == str(euler_live.user_id)

            sent = await client.api.group(str(euler_live.group_id)).send(
                Message(Text(text="HyperBotCore V2 live test"))
            )
            await asyncio.sleep(1)
            await client.api.message(sent.message_id).recall()
        finally:
            await client.stop()

    asyncio.run(run())
