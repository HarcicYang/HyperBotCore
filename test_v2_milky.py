"""V2 smoke test for the Milky adapter.

Same flow as ``test_v2.py`` (which uses the OneBot adapter), pointed at a Milky
protocol end: reply ``pong`` to ``.ping``, then send a quoted message with a mention,
text and the banner image, and recall the first reply after three seconds.

Run it with::

    python test_v2_milky.py

The config path defaults to ``appconfig.milky.json`` and can be overridden with the
``HYPEROT_CONFIG`` environment variable.
"""

import asyncio
import os
from pathlib import Path

from hyperot.v2 import Client, Image, Mention, Message, Quote, Text
from hyperot.v2.events import MessageReceivedEvent

CONFIG_FILE = os.environ.get("HYPEROT_CONFIG", "appconfig.milky.json")
BANNER = Path(__file__).resolve().parent / "ban.png"
# Seconds to wait before recalling the first reply, so the message stays visible long
# enough to read. Tests can shorten it through the environment.
RECALL_DELAY = float(os.environ.get("HYPEROT_RECALL_DELAY", "3"))


async def handler_msg(event: MessageReceivedEvent, client: Client) -> None:
    if str(event.message) != ".ping":
        return

    scene = client.api.scene(event.scene_type, event.scene_id)
    version = await client.api.bot.version()
    result = await scene.send("pong")

    segments = [
        Quote(message_id=str(result.message_id)),
        Text(text=f" Hello from HyperBotCore V2 {version.app_version} (Milky {version.protocol_version})"),
        Image(
            source=f"file://{BANNER}",
            alt="HyperBotCore Banner",
        ),
    ]
    if event.user_id is not None:
        segments.insert(1, Mention(user_id=event.user_id))

    await scene.send(Message(*segments))
    await asyncio.sleep(RECALL_DELAY)
    await client.api.message(result.message_id).recall()


async def main() -> None:
    print(f"[test_v2_milky] config={CONFIG_FILE}")
    client = Client.from_appconfig(CONFIG_FILE)
    client.subscribe(MessageReceivedEvent, handler_msg)
    await client.run()


if __name__ == "__main__":
    asyncio.run(main())
