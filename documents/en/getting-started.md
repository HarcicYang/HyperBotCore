# Getting Started

## Installation

```shell
pip install hyper-bot
```

For development, HyperBotCore supports [uv](https://docs.astral.sh/uv/):

```shell
git clone <repo-url>
cd HyperBotCore
uv sync
```

## Protocol Implementations

HyperBotCore supports both the OneBot v11 and [Milky](configuration.md) protocols, switched via the `protocol` field in `config.json`.

### OneBot v11 Implementations

- [NapCat](https://github.com/NapNeko/NapCatQQ)
- [LLOneBot](https://github.com/LLOneBot/LLOneBot)
- [Lagrange.OneBot](https://github.com/LagrangeDev/Lagrange.Core)
- [EulerOneBot](https://github.com/HarcicYang/EulerOneBot)

### Milky Implementations

- [Lagrange.Milky](https://github.com/LagrangeDev/Lagrange.Core)
- [Yogurt](https://acidify.ntqqrev.org/yogurt/start)

See [Configuration](configuration.md) for Milky setup and [Events](events.md) for event mapping.

## Quick Start

1. Create `config.json` (see [Configuration](configuration.md)); for Milky, create `milky_config.json` and call `hyperot.init("milky_config.json")`

2. Write your bot:

```python
import asyncio
import hyperot

hyperot.init()  # Load config, initialize adapter

from hyperot import Client
from hyperot.events import GroupMessageEvent

async def handler(event, actions):
    if str(event.message) == ".ping":
        await actions.send_msg(
            f"pong! HypeR Core {hyperot.HYPER_BOT_VERSION}",
            group_id=event.group_id,
            user_id=event.user_id
        )

with Client() as cli:
    cli.subscribe(handler, GroupMessageEvent)
    asyncio.get_event_loop().run_until_complete(cli.run())
```

3. Start your protocol implementation, then run your bot script.
