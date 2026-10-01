# 从 V1 迁移到 V2

V2 和 V1 可以在同一个项目里并存，不需要一次性改完。V2 使用 `hyperot.v2`，V1 仍然使用原来的 `hyperot.*`。

## 迁移前先知道

V2 的主要变化：

- 一个 `Client` 管理一个账号和一个适配器。
- 配置从 `config.json` 变成 `appconfig.json`。
- 适配器通过独立包安装。
- API 从 `actions` 对象变成 `client.api` 分层调用。
- 事件处理器仍然是异步函数，但参数是 `(event, client)`。
- 不再使用全局 `hyperot.init()`。

## 安装变化

V1：

```shell
pip install hyper-bot
```

V2：

```shell
pip install hyper-bot <adapter-package>
```

框架和适配器分开安装。以后升级适配器时，不需要替换整个框架仓库。

## 配置变化

V1 使用 `config.json`，V2 使用 `appconfig.json`。

V2 示例：

```json
{
  "schema_version": 1,
  "active_adapter": "<adapter-id>",
  "adapter_config": {}
}
```

完整字段见[配置](configuration.md)。适配器相关字段见[适配器文档](../adapters/index.md)。

## 启动方式变化

V1 常见写法：

```python
import hyperot

hyperot.init()
client = Client()
```

V2：

```python
from hyperot.v2 import Client

client = Client.from_appconfig("appconfig.json")
```

没有全局初始化，配置属于当前 `Client`。

## 事件处理变化

V1 的处理器通常是：

```python
async def handler(event, actions):
    await actions.send_msg("hello", group_id=event.group_id)
```

V2：

```python
from hyperot.v2.events import MessageReceivedEvent


async def handler(event: MessageReceivedEvent, client: Client) -> None:
    await client.api.scene(event.scene_type, event.scene_id).send("hello")
```

主要区别：

- 第二个参数从 `actions` 变成 `client`。
- 操作通过 `client.api` 调用。
- 回复当前场景使用 `scene()`，不用自己判断群聊和私聊。

## 订阅方式变化

V1：

```python
client.subscribe(handler, GroupMessageEvent)
```

V2：

```python
client.subscribe(MessageReceivedEvent, handler)
```

注意参数顺序：先事件类型，后处理器。

## API 调用变化

V1：

```python
await actions.send_msg("hello", group_id=123456)
await actions.get_group_info(group_id=123456)
await actions.set_group_ban(group_id=123456, user_id=10001, duration=600)
```

V2：

```python
await client.api.group("123456").send("hello")
await client.api.group("123456").profile()
await client.api.group("123456").member("10001").mute(600)
```

V2 的 API 更接近业务动作，不需要一直传 `group_id` 和 `user_id`。

群号、用户号、消息号等参数可以直接写字符串或整数，不需要手动构造 ID 类型。

## 消息变化

V1 和 V2 都使用 `Message` 和消息段，但 V2 的公共消息段更精简，也更强调协议无关：

- `Text`
- `Mention`
- `MentionAll`
- `Image`
- `Audio`
- `Video`
- `File`
- `Quote`
- `Forward`
- `ForwardNode`
- `Face`
- `Markdown`

V2 的消息和消息段是标准库 dataclass，不再基于 pydantic：

- `Message(Text("hi"), Image("u"))` 与 V1 的 `*args` 写法一致，也接受段列表和元组。
- 消息段不可变，`model_dump()`、`model_validate()` 不再提供，段之间用 `==` 比较。
- 自定义消息段需要注册进适配器的段注册表，见[消息与消息段](messages.md)。

见[消息与消息段](messages.md)。

## 推荐迁移顺序

1. 先安装对应适配器包。
2. 新建 `appconfig.json`，先只迁移连接配置。
3. 把机器人入口改成 `Client.from_appconfig()`。
4. 把事件订阅改成 V2 的 `(event_type, handler)` 顺序。
5. 把 `actions.send_msg()` 等调用逐步改成 `client.api`。
6. 最后处理协议特有的高级功能，例如原始 API、特殊事件和扩展能力。

迁移过程中可以保留 V1 代码，先让 V2 跑通新功能，再逐步替换旧功能。
