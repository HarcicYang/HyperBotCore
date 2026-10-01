# 事件

事件是机器人收到的“发生了什么”。消息、群成员变化、好友请求、连接状态变化，都会以事件的形式进入你的 handler。

## 事件处理器

```python
from hyperot.v2 import Client
from hyperot.v2.events import MessageReceivedEvent


async def on_message(event: MessageReceivedEvent, client: Client) -> None:
    await client.api.scene(event.scene_type, event.scene_id).send("收到")


client.subscribe(MessageReceivedEvent, on_message)
```

处理器必须是异步函数。不同处理器会并发执行，一个处理器变慢不会卡住其他处理器。

## 公共字段

所有事件都有：

| 字段 | 说明 |
| --- | --- |
| `timestamp` | 事件发生时间。 |
| `event_id` | 本次事件在本进程内的唯一 ID。 |

场景事件还包含：

| 字段 | 说明 |
| --- | --- |
| `scene_type` | 场景类型，通常是群聊或私聊。 |
| `scene_id` | 场景 ID。群聊时是群号，私聊时是对方用户号。 |
| `user_id` | 触发事件的人。群聊里是发言者，私聊里是对方。 |

回复当前场景时，推荐直接使用：

```python
await client.api.scene(event.scene_type, event.scene_id).send("回复内容")
```

这样群聊、私聊都不用单独判断。

## 消息事件

### MessageReceivedEvent

收到私聊或群聊消息。

常用字段：

| 字段 | 说明 |
| --- | --- |
| `message_id` | 消息 ID。 |
| `message` | 消息内容，类型是 `Message`。 |
| `sender` | 发送者信息，可能包含昵称、群名片、角色、头衔等。 |
| `is_mentioned` | 机器人是否被 @。 |

示例：

```python
async def on_message(event: MessageReceivedEvent, client: Client) -> None:
    text = str(event.message)

    if text == ".ping":
        await client.api.scene(event.scene_type, event.scene_id).send("pong")
        return

    if event.is_mentioned:
        await client.api.scene(event.scene_type, event.scene_id).send("你叫我了？")
```

### MessageRecalledEvent

消息被撤回。

| 字段 | 说明 |
| --- | --- |
| `message_id` | 被撤回的消息 ID。 |
| `operator_id` | 执行撤回的人，可能为空。 |

### MessageReactionChangedEvent

消息表情回应发生变化。

| 字段 | 说明 |
| --- | --- |
| `message_id` | 被回应的消息 ID。 |
| `reaction` | 表情或表情 ID。 |
| `added` | `true` 表示新增，`false` 表示取消。 |
| `count` | 当前数量，可能为空。 |

## 群成员与群状态

| 事件 | 说明 | 常用字段 |
| --- | --- | --- |
| `MemberJoinedEvent` | 成员加入群聊。 | `member_id`、`operator_id`、`inviter_id` |
| `MemberLeftEvent` | 成员离开群聊。 | `member_id`、`operator_id`、`kicked` |
| `MemberMuteChangedEvent` | 成员被禁言或解除禁言。 | `member_id`、`operator_id`、`muted`、`duration` |
| `MemberRoleChangedEvent` | 成员角色变化。 | `member_id`、`operator_id`、`old_role`、`new_role` |
| `GroupNameChangedEvent` | 群名变化。 | `old_name`、`new_name`、`operator_id` |
| `GroupMuteChangedEvent` | 全员禁言状态变化。 | `muted`、`duration`、`operator_id` |

示例：

```python
from hyperot.v2.events import MemberJoinedEvent


async def welcome(event: MemberJoinedEvent, client: Client) -> None:
    await client.api.scene(event.scene_type, event.scene_id).send(
        f"欢迎 {event.member_id} 加入群聊"
    )
```

## 文件与精华消息

### FileUploadedEvent

有人上传文件。

| 字段 | 说明 |
| --- | --- |
| `file` | 文件信息，包含文件 ID、文件名、大小。 |

### EssenceChangedEvent

精华消息发生变化。

| 字段 | 说明 |
| --- | --- |
| `message_id` | 消息 ID。 |
| `operator_id` | 操作者。 |
| `added` | `true` 表示设为精华，`false` 表示取消精华。 |

## 戳一戳

### PokeReceivedEvent

有人戳了机器人或群成员。

| 字段 | 说明 |
| --- | --- |
| `target_id` | 被戳的人。 |
| `display_action` | 展示动作，可能为空。 |
| `display_suffix` | 展示后缀，可能为空。 |
| `display_image_url` | 展示图片，可能为空。 |

## 请求事件

| 事件 | 说明 | 常用字段 |
| --- | --- | --- |
| `FriendRequestedEvent` | 收到好友请求。 | `request_id`、`user_id`、`comment` |
| `FriendAddedEvent` | 已成为好友。 | `user_id` |
| `GroupJoinRequestedEvent` | 有人申请加群。 | `request_id`、`inviter_id`、`comment` |
| `GroupInvitationReceivedEvent` | 机器人被邀请入群。 | `request_id`、`inviter_id`、`source_group_id` |
| `GroupMemberInviteRequestedEvent` | 邀请其他成员入群。 | `request_id`、`inviter_id`、`target_user_id` |

处理请求时，把 `request_id` 交给 API：

```python
from hyperot.v2.events import FriendRequestedEvent


async def on_friend_request(event: FriendRequestedEvent, client: Client) -> None:
    await client.api.friend_request(event.request_id).approve()
```

## 框架事件

| 事件 | 说明 |
| --- | --- |
| `ClientStartedEvent` | 客户端启动完成。 |
| `ClientStoppedEvent` | 客户端已停止。 |
| `BotOnlineEvent` | 机器人上线。 |
| `BotOfflineEvent` | 机器人离线。 |

这些事件适合做状态记录、通知或资源初始化。

## 适配器差异

公共事件不包含某个协议的专有字段。适配器可能会提供更具体的子类或额外事件，例如协议原始字段、心跳和特殊通知。

业务代码建议优先使用本页列出的公共字段；只有确实需要协议专有能力时，再使用适配器提供的额外事件。

另外，不是每个适配器都会产生本页列出的全部事件。实际能收到哪些事件，取决于协议端和适配器的支持范围。
