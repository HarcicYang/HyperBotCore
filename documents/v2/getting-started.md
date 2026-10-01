# V2 快速开始

这一页会让你跑起来一个最小机器人。V2 本体不绑定具体协议，你需要额外安装一个适配器。

## 1. 安装

需要 Python 3.11 或更高版本。

```shell
pip install hyper-bot
```

`hyper-bot` 是框架本体。接下来安装你要使用的适配器：

```shell
pip install <adapter-package>
```

适配器可以单独安装和升级，不需要把整个框架仓库复制到项目里。可用适配器见[适配器文档](../adapters/index.md)。

## 2. 准备协议端

启动你要连接的协议端，并按适配器文档完成连接配置。

## 3. 创建 `appconfig.json`

在机器人项目目录创建 `appconfig.json`。顶层结构固定，`adapter_config` 的内容由当前适配器决定：

```json
{
  "schema_version": 1,
  "active_adapter": "<adapter-id>",
  "adapter_config": {},
  "runtime": {
    "reconnect_max_attempts": 5,
    "action_timeout": 30.0
  },
  "logging": {
    "level": "INFO",
    "stream": "stdout"
  }
}
```

`active_adapter` 填已安装适配器的 ID，`adapter_config` 按对应适配器文档填写。V2 顶层配置见[配置](configuration.md)。

## 4. 写机器人

```python
import asyncio

from hyperot.v2 import Client
from hyperot.v2.events import MessageReceivedEvent


async def on_message(event: MessageReceivedEvent, client: Client) -> None:
    if str(event.message) != ".ping":
        return

    await client.api.scene(event.scene_type, event.scene_id).send("pong")


async def main() -> None:
    client = Client.from_appconfig("appconfig.json")
    client.subscribe(MessageReceivedEvent, on_message)
    await client.run()


asyncio.run(main())
```

运行：

```shell
python bot.py
```

现在私聊机器人或群聊里发送 `.ping`，机器人会回复 `pong`。

## 5. 代码在做什么

- `Client.from_appconfig()` 读取配置，并根据 `active_adapter` 加载已安装的适配器。
- `client.subscribe(MessageReceivedEvent, on_message)` 订阅所有消息事件。
- `event.scene_type` 和 `event.scene_id` 表示消息来自哪里，直接用它回复最方便。
- `client.run()` 会启动机器人并一直运行，直到进程收到停止信号或发生不可恢复的错误。

## 6. 接下来看什么

- 想了解事件字段：[事件](events.md)
- 想发送图片、@ 或引用消息：[消息与消息段](messages.md)
- 想管理群、查询资料、处理请求：[API](api.md)
- 想了解启动和停止：[Client 与生命周期](client.md)
- 想选择或配置适配器：[适配器文档](../adapters/index.md)
