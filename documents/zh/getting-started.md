# 快速开始

## 安装

```shell
pip install hyper-bot
```

开发环境使用 [uv](https://docs.astral.sh/uv/)：

```shell
git clone <repo-url>
cd HyperBotCore
uv sync
```

## 协议实现

HypeR Core 支持 OneBot v11 与 [Milky](milky.md) 两种协议，通过 `config.json` 的 `protocol` 字段切换。

### OneBot v11 实现

- [NapCat](https://github.com/NapNeko/NapCatQQ)
- [LLOneBot](https://github.com/LLOneBot/LLOneBot)
- [Lagrange.OneBot](https://github.com/LagrangeDev/Lagrange.Core)

### Milky 实现

- [Lagrange.Milky](https://github.com/LagrangeDev/Lagrange.Core)
- [Yogurt](https://acidify.ntqqrev.org/yogurt/start)

Milky 模式的配置与使用见 [Milky 协议](milky.md)。

## 快速开始

1. 创建 `config.json`（详见[配置文件](configuration.md)）；使用 Milky 协议则创建 `milky_config.json` 并调用 `hyperot.init("milky_config.json")`

2. 编写机器人：

```python
import asyncio
import hyperot

hyperot.init()  # 加载配置、初始化适配器

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

3. 启动协议端实现，再运行你的 bot 脚本。
