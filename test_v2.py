import asyncio
import os
from pathlib import Path

from hyperot.v2 import Client, Image, Mention, Message, Quote, Text
from hyperot.v2.events import MessageReceivedEvent

CONFIG_FILE = os.environ.get("HYPEROT_CONFIG", "appconfig.json")


async def handler_msg(event: MessageReceivedEvent, client: Client) -> None:
    if str(event.message) != ".ping":
        return

    scene = client.api.scene(event.scene_type, event.scene_id)
    version = await client.api.bot.version()
    result = await scene.send("pong")

    segments = [
        Quote(message_id=str(result.message_id)),
        Text(text=f" Hello from HyperBotCore V2 {version.app_version}"),
        Image(
            source=f"file://{Path('ban.png').resolve()}",
            alt="HyperBotCore Banner",
        ),
    ]
    if event.user_id is not None:
        segments.insert(1, Mention(user_id=event.user_id))

    await scene.send(Message(*segments))
    await asyncio.sleep(3)
    await client.api.message(result.message_id).recall()


async def main() -> None:
    client = Client.from_appconfig(CONFIG_FILE)
    client.subscribe(MessageReceivedEvent, handler_msg)
    await client.run()


if __name__ == "__main__":
    asyncio.run(main())
