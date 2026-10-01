# Client 与生命周期

`Client` 是 V2 的入口。一个 `Client` 管理一个机器人账号、一个适配器和一组事件处理器。

## 创建 Client

最常用的方式是从配置文件创建：

```python
from hyperot.v2 import Client

client = Client.from_appconfig("appconfig.json")
```

也可以手动传入适配器对象和配置，适合测试或更复杂的启动流程。具体构造方式由适配器文档决定。日常使用推荐 `from_appconfig()`，这样安装哪个适配器、使用哪种连接都只改配置文件。

## 订阅事件

事件处理器必须是异步函数，接收两个参数：事件对象和当前 `Client`。

```python
from hyperot.v2.events import MessageReceivedEvent


async def on_message(event: MessageReceivedEvent, client: Client) -> None:
    print(event.scene_type, event.scene_id, event.message)


client.subscribe(MessageReceivedEvent, on_message)
```

同一个事件类型可以订阅多个处理器。它们会并发执行，互不阻塞。

```python
client.subscribe(MessageReceivedEvent, log_message)
client.subscribe(MessageReceivedEvent, reply_ping)
```

取消订阅：

```python
client.unsubscribe(MessageReceivedEvent, on_message)
```

## 启动和停止

### run()

最常用：

```python
await client.run()
```

`run()` 会启动客户端，然后一直运行到收到停止信号或发生不可恢复的错误。它适合作为机器人程序的主入口。

### start() / stop()

如果你需要自己控制生命周期：

```python
await client.start()

# 在这里做其他事情

await client.stop()
```

`start()` 启动后不会阻塞。适合嵌入 FastAPI、Web 服务或其他已有事件循环。

### 异步上下文管理器

```python
async with Client.from_appconfig("appconfig.json") as client:
    client.subscribe(MessageReceivedEvent, on_message)
    await client.run()
```

离开 `async with` 时会自动停止。

## 手动触发事件

有时你希望把外部事件送进同一套事件系统：

```python
from datetime import UTC, datetime

from hyperot.v2.common import SceneType
from hyperot.v2.events import MessageReceivedEvent
from hyperot.v2.messages import Message, Text


event = MessageReceivedEvent(
    timestamp=datetime.now(UTC),
    scene_type=SceneType.GROUP,
    scene_id="123456",
    user_id="10001",
    message_id="local-1",
    message=Message(Text(text="来自外部系统的消息")),
)

await client.emit(event)
```

手动事件会像普通事件一样进入订阅和日志流程。

## 扩展能力

部分适配器会提供额外接口。可以通过 `client.extension()` 获取：

```python
extension = client.extension(SomeAdapterInterface)
```

没有对应扩展时会抛出异常。普通机器人开发一般不需要用到它。

## 常见问题

### 为什么没有全局 init？

V2 不使用全局初始化。配置、适配器和事件订阅都属于当前 `Client` 实例。这样多实例、测试和依赖注入都更简单。

### 一个 Client 能连多个账号吗？

不能。一个 `Client` 对应一个账号和一个适配器。多账号请启动多个 `Client`，通常放在不同进程里。

### 断线会自动重连吗？

会。重连次数由 `runtime.reconnect_max_attempts` 控制。设为 `null` 表示无限重连，达到上限后 `run()` 会退出并抛出错误。

连接失败和断开时的错误信息会带上具体地址和原因，可以直接用来定位：连接被拒绝、域名解析失败、证书问题、握手被拒绝各有对应提示。重试用尽时最后一条 Error 日志会提示把 `reconnect_max_attempts` 设为 `null` 可以继续重试。
