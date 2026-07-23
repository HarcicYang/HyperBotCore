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

## OneBot Implementation

HyperBotCore adapts the OneBot v11 protocol. You need a compatible implementation running:

- [NapCat](https://github.com/NapNeko/NapCatQQ)
- [LLOneBot](https://github.com/LLOneBot/LLOneBot)
- [Lagrange.OneBot](https://github.com/LagrangeDev/Lagrange.Core)

## Quick Start

1. Create `config.json` (see [Configuration](configuration.md))

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

3. Start your OneBot implementation, then run your bot script.
