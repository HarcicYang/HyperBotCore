# API

V2 的操作入口是 `client.api`。它按场景、用户、群、消息、请求等对象分层，读起来更接近你实际想做的事。

## 发送消息

### 回复当前场景

事件处理器里最常用：

```python
await client.api.scene(event.scene_type, event.scene_id).send("回复内容")
```

群聊和私聊都可以用这一种写法。

### 发到指定群或用户

```python
await client.api.group("123456").send("群消息")
await client.api.user(10001).send("私聊消息")
```

`send()` 可以直接接收字符串，也可以接收 [Message](messages.md)。

群号、用户号、消息号等参数可以直接写字符串或整数，不需要手动包装。

## 群

```python
group = client.api.group("123456")
```

| 操作 | 说明 |
| --- | --- |
| `await group.send(message)` | 发送群消息。 |
| `await group.profile()` | 获取群资料。 |
| `await group.members()` | 获取群成员列表。 |
| `await group.set_name(name)` | 修改群名。 |
| `await group.mute_all()` | 开启全员禁言。 |
| `await group.unmute_all()` | 关闭全员禁言。 |
| `await group.leave()` | 退出群聊。 |

群成员：

```python
member = group.member("10001")

await member.profile()
await member.kick()
await member.mute(600)
await member.unmute()
await member.set_card("新群名片")
await member.set_title("群头衔")
```

## 用户

```python
user = client.api.user("10001")

profile = await user.profile()
await user.send("你好")
```

## 消息

```python
message = client.api.message(message_id)

await message.fetch()
await message.quote()
await message.recall()
await message.react("👍")
await message.unreact("👍")
await message.set_essence()
await message.remove_essence()
```

`quote()` 会读取原消息并返回一个引用消息段，可以直接放进新消息里。

## 请求

好友请求：

```python
await client.api.friend_request(request_id).approve()
await client.api.friend_request(request_id).reject("暂时不加好友")
```

群请求和群邀请：

```python
await client.api.group_request(request_id).approve()
await client.api.group_request(request_id).reject("不通过")
```

请求事件里会带有 `request_id`，直接传给对应 API 即可。

## 机器人状态

```python
profile = await client.api.bot.profile()
status = await client.api.bot.status()
version = await client.api.bot.version()
```

## 文件

公共文件 API 有：

```python
await client.api.file(file_id).info()
await client.api.file(file_id).download()
```

不同适配器支持程度不同。协议特有的文件能力，请查看对应适配器文档。

## 调用未封装的 API

如果当前适配器支持某个 API，但框架还没有为它提供专门方法，可以直接调用：

```python
result = await client.api.raw("some_action", {"arg1": "value"})

print(result.data)
```

`raw()` 返回 `RawResult`，原始内容在 `.data` 里。它适合协议扩展或临时操作，不适合替代稳定的公共 API。

适配器自己提供的扩展 API 见[适配器文档](../adapters/index.md)。

## 返回值

V2 的 API 返回类型化对象，而不是裸字典。

| 类型 | 常用字段 |
| --- | --- |
| `SendResult` | `message_id` |
| `UserProfile` | `user_id`、`display_name`、`sex`、`age` |
| `FriendInfo` | `user_id`、`display_name` |
| `GroupProfile` | `group_id`、`name`、`member_count`、`max_member_count` |
| `GroupMemberProfile` | `group_id`、`user_id`、`display_name`、`card`、`role` |
| `BotProfile` | `user_id`、`display_name` |
| `BotStatus` | `online`、`good`、`app_good`、`memory` |
| `VersionInfo` | `app_name`、`app_version`、`protocol_version` |
| `FileUrl` | `url` |
| `RawResult` | `data` |

示例：

```python
sent = await client.api.group(group_id).send("hello")
print(sent.message_id)
```

## 错误处理

API 失败会抛出异常。常见做法：

```python
from hyperot.v2.common import ActionRejectedError, ActionTimeoutError

try:
    await client.api.group(group_id).send("hello")
except ActionTimeoutError:
    print("协议端响应超时")
except ActionRejectedError as exc:
    print("协议端拒绝了请求", exc)
```

更多异常见[进阶用法](advanced.md)。
