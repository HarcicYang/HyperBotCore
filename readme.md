![banner](./ban.png)

<div align="center">
<h1>HypeR Core</h1>
</div>
<p align="center">适配 OneBot v11 协议，目标多协议、功能模块化、易于扩展、高效的 QQ 机器人框架</p>
<div align="center">
<img src="https://img.shields.io/badge/OneBot-11-black?logo=data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAHAAAABwCAMAAADxPgR5AAAAGXRFWHRTb2Z0d2FyZQBBZG9iZSBJbWFnZVJlYWR5ccllPAAAAAxQTFRF////29vbr6+vAAAAk1hCcwAAAAR0Uk5T////AEAqqfQAAAKcSURBVHja7NrbctswDATQXfD//zlpO7FlmwAWIOnOtNaTM5JwDMa8E+PNFz7g3waJ24fviyDPgfhz8fHP39cBcBL9KoJbQUxjA2iYqHL3FAnvzhL4GtVNUcoSZe6eSHizBcK5LL7dBr2AUZlev1ARRHCljzRALIEog6H3U6bCIyqIZdAT0eBuJYaGiJaHSjmkYIZd+qSGWAQnIaz2OArVnX6vrItQvbhZJtVGB5qX9wKqCMkb9W7aexfCO/rwQRBzsDIsYx4AOz0nhAtWu7bqkEQBO0Pr+Ftjt5fFCUEbm0Sbgdu8WSgJ5NgH2iu46R/o1UcBXJsFusWF/QUaz3RwJMEgngfaGGdSxJkE/Yg4lOBryBiMwvAhZrVMUUvwqU7F05b5WLaUIN4M4hRocQQRnEedgsn7TZB3UCpRrIJwQfqvGwsg18EnI2uSVNC8t+0QmMXogvbPg/xk+Mnw/6kW/rraUlvqgmFreAA09xW5t0AFlHrQZ3CsgvZm0FbHNKyBmheBKIF2cCA8A600aHPmFtRB1XvMsJAiza7LpPog0UJwccKdzw8rdf8MyN2ePYF896LC5hTzdZqxb6VNXInaupARLDNBWgI8spq4T0Qb5H4vWfPmHo8OyB1ito+AysNNz0oglj1U955sjUN9d41LnrX2D/u7eRwxyOaOpfyevCWbTgDEoilsOnu7zsKhjRCsnD/QzhdkYLBLXjiK4f3UWmcx2M7PO21CKVTH84638NTplt6JIQH0ZwCNuiWAfvuLhdrcOYPVO9eW3A67l7hZtgaY9GZo9AFc6cryjoeFBIWeU+npnk/nLE0OxCHL1eQsc1IciehjpJv5mqCsjeopaH6r15/MrxNnVhu7tmcslay2gO2Z1QfcfX0JMACG41/u0RrI9QAAAABJRU5ErkJggg==" alt="OneBot V11">
<img src="https://img.shields.io/static/v1?label=LICENSE&message=GPL-3.0&color=lightrey" alt="GPL-3.0">
<img src="https://img.shields.io/pypi/v/hyper-bot?label=pypi&color=blue" alt="Pypi">
</div>

## 概览

HypeR Core 是一个基于 Python asyncio 的 OneBot v11 机器人框架，提供简洁的事件系统、消息构建器和类型安全的 API 响应。

[English Documentation](./documents/en.md)
[中文文档](./documents/zh.md)

---

## 安装

```shell
pip install hyper-bot
```

开发和构建使用 [uv](https://docs.astral.sh/uv/)：

```shell
git clone https://github.com/HarcicYang/HypeR_Bot
cd HyperBotCore
uv sync
```

## 文档

- [快速开始](./documents/zh/getting-started.md)
- [配置文件](./documents/zh/configuration.md)
- [Client 与生命周期](./documents/zh/client.md)
- [事件系统](./documents/zh/events.md)
- [消息与消息段](./documents/zh/messages.md)
- [Actions API 操作](./documents/zh/actions.md)
- [高级用法](./documents/zh/advanced.md)

## 简单示例

```python
import asyncio
import hyperot

hyperot.init()

from hyperot import Client
from hyperot.events import GroupMessageEvent, PrivateMessageEvent
from hyperot.common import Message
from hyperot.segments import *

async def handler(event, actions):
    if str(event.message) == ".ping":
        await actions.send_msg(
            f"pong! HypeR Core {hyperot.HYPER_BOT_VERSION}",
            group_id=event.group_id,
            user_id=event.user_id
        )

with Client() as cli:
    cli.subscribe(handler, [GroupMessageEvent, PrivateMessageEvent])
    asyncio.get_event_loop().run_until_complete(cli.run())
```

## 许可

GPL-3.0 License

