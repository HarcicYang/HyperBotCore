"""V2 smoke test for the Satori adapter.

Same flow as ``test_v2.py`` (which uses the OneBot adapter), pointed at a Satori
protocol end: reply ``pong`` to ``.ping``, then send a quoted message with a mention,
text and the banner image, and recall the first reply after three seconds.

Two things differ from the OneBot and Milky scripts, because the protocol does:

- Satori has no version API, so the script falls back to the bot profile.
- Satori message elements reference resources by URL, so the banner is uploaded with
  ``upload.create`` first and a plain ``file://`` URL is used only if that fails.

Run it with::

    python test_v2_satori.py

The config path defaults to ``appconfig.satori.json`` and can be overridden with the
``HYPEROT_CONFIG`` environment variable.
"""

import asyncio
import os
from pathlib import Path

from hyperot.v2 import Client, Image, Mention, Message, Quote, Text
from hyperot.v2.common import CapabilityNotSupportedError, HyperotError
from hyperot.v2.events import MessageReceivedEvent

CONFIG_FILE = os.environ.get("HYPEROT_CONFIG", "appconfig.satori.json")
BANNER = Path(__file__).resolve().parent / "ban.png"
# Seconds to wait before recalling the first reply, so the message stays visible long
# enough to read. Tests can shorten it through the environment.
RECALL_DELAY = float(os.environ.get("HYPEROT_RECALL_DELAY", "3"))


async def bot_label(client: Client) -> str:
    """Return something printable describing the account behind this connection."""
    try:
        version = await client.api.bot.version()
    except CapabilityNotSupportedError:
        # The Satori protocol has no version API; the login is the next best thing.
        profile = await client.api.bot.profile()
        return profile.display_name or profile.user_id
    return f"{version.app_name} {version.app_version}"


async def banner_source(client: Client) -> str:
    """Return a URL for the banner, uploading it when the adapter supports that."""
    upload = getattr(client.api, "upload", None)
    if upload is not None:
        try:
            uploaded = await upload({"banner": str(BANNER)})
        except HyperotError as exc:
            print(f"[test_v2_satori] upload.create failed, using a file URL: {exc}")
        else:
            if uploaded.get("banner"):
                return uploaded["banner"]
    return f"file://{BANNER}"


async def handler_msg(event: MessageReceivedEvent, client: Client) -> None:
    if str(event.message) != ".ping":
        return

    scene = client.api.scene(event.scene_type, event.scene_id)
    label = await bot_label(client)
    result = await scene.send("pong")
    source = await banner_source(client)

    segments = [
        Quote(message_id=str(result.message_id)),
        Text(text=f" Hello from HyperBotCore V2 {label}"),
        Image(source=source, alt="HyperBotCore Banner"),
    ]
    if event.user_id is not None:
        segments.insert(1, Mention(user_id=event.user_id))

    await scene.send(Message(*segments))
    await asyncio.sleep(RECALL_DELAY)
    await client.api.message(result.message_id).recall()


async def main() -> None:
    print(f"[test_v2_satori] config={CONFIG_FILE}")
    client = Client.from_appconfig(CONFIG_FILE)
    client.subscribe(MessageReceivedEvent, handler_msg)
    await client.run()


if __name__ == "__main__":
    asyncio.run(main())
