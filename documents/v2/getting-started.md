# V2 快速开始

```shell
pip install hyper-bot hyperot-adapter-onebot
```

```python
import asyncio

from hyperot.v2 import Client
from hyperot.v2.events import MessageReceivedEvent


async def handler(event: MessageReceivedEvent, client: Client) -> None:
    if str(event.message) == ".ping":
        await client.api.scene(event.scene_type, event.scene_id).send("pong")


async def main() -> None:
    client = Client.from_appconfig("appconfig.json")
    client.subscribe(MessageReceivedEvent, handler)
    await client.run()


asyncio.run(main())
```

`Client` 没有全局 `init()`。配置、适配器和事件注册表均属于当前 Client 实例。
