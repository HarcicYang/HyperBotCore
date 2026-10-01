![banner](./ban.png)

<div align="center">
<h1>HypeR Core</h1>
</div>

<p align="center">基于 Python asyncio 的 QQ 机器人框架。V2 采用协议无关核心与独立适配器，V1 继续可用。</p>

<div align="center">
<img src="https://img.shields.io/badge/Python-3.11%2B-blue" alt="Python 3.11+">
<img src="https://img.shields.io/static/v1?label=LICENSE&message=GPL-3.0&color=lightrey" alt="GPL-3.0">
<img src="https://img.shields.io/pypi/v/hyper-bot?label=pypi&color=blue" alt="Pypi">
</div>

## 概览

HypeR Core 是一个基于 Python asyncio 的 QQ 机器人框架，提供事件系统、消息构建和类型化 API。

V1 继续保留原有接口和内置协议支持。V2 使用独立的 `hyperot.v2` 命名空间，把框架核心和协议适配器分开维护：

- 框架本体只负责事件、消息、API 和生命周期。
- 具体协议通过独立适配器包接入。
- 不同适配器有自己的连接配置、事件映射和扩展能力。
- 业务代码优先使用协议无关的公共事件和 `client.api`。

## V2

V2 使用一个 `Client` 管理一个适配器：

```python
import asyncio

from hyperot.v2 import Client
from hyperot.v2.events import MessageReceivedEvent


async def on_message(event: MessageReceivedEvent, client: Client) -> None:
    if str(event.message) == ".ping":
        await client.api.scene(event.scene_type, event.scene_id).send("pong")


async def main() -> None:
    client = Client.from_appconfig("appconfig.json")
    client.subscribe(MessageReceivedEvent, on_message)
    await client.run()


asyncio.run(main())
```

适配器单独安装。例如使用 OneBot v11：

```shell
pip install hyper-bot hyperot-adapter-onebot
```

具体安装、连接配置和扩展能力见[适配器文档](./documents/adapters/index.md)。

---

## 文档

- [V2 文档](./documents/v2/index.md)：配置、Client、事件、消息、API 和迁移。
- [适配器文档](./documents/adapters/index.md)：各适配器的安装和使用说明。
- [V1 中文文档](./documents/zh.md)：旧版接口和内置协议。

## 安装

需要 Python 3.11 或更高版本。

框架本体：

```shell
pip install hyper-bot
```

再安装一个适配器，例如：

```shell
pip install hyperot-adapter-onebot
```

## 开发

开发和构建使用 [uv](https://docs.astral.sh/uv/)：

```shell
git clone https://github.com/HarcicYang/HyperBotCore
cd HyperBotCore
uv sync
```

## 许可

GPL-3.0 License
