# HyperBotCore V2

V2 是一套面向实际机器人开发的新接口。它和 V1 同时存在，但使用独立的 `hyperot.v2` 命名空间，可以逐步迁移。

如果你第一次接触这个框架，建议按下面的顺序阅读：

1. [快速开始](getting-started.md)：安装、配置并跑起第一个机器人。
2. [配置](configuration.md)：完整了解 `appconfig.json`。
3. [Client 与生命周期](client.md)：启动、停止、订阅事件和手动发事件。
4. [事件](events.md)：收到消息、群成员变化、请求等事件后怎么处理。
5. [消息与消息段](messages.md)：构造文本、图片、@、引用和转发消息。
6. [API](api.md)：发送消息、管理群、查询资料和处理请求。
7. [适配器](../adapters/index.md)：选择并配置具体协议适配器。
8. [进阶用法](advanced.md)：日志、异常、重连、自定义适配器。
9. [从 V1 迁移](migration.md)：把旧代码迁移到 V2。

## V2 是什么

V2 的核心思路很简单：

- 一个 `Client` 管理一个机器人账号和一个适配器。
- 事件从适配器进入你的 handler，handler 是异步函数。
- 需要操作机器人时，通过 `client.api` 调用。
- 公共事件和消息不绑定具体协议；不同协议的差异由适配器处理。

## 最小示例

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

## 相关链接

- [项目主页](../../readme.md)
- [适配器文档](../adapters/index.md)
