# Milky 协议

[Milky](https://milky.ntqqrev.org/) 是基于 HTTP / WebSocket 通信的新一代 QQ 机器人接口标准。HypeR Core 作为应用端：通过 WebSocket 接收事件推送（`/event`），通过 HTTP 调用协议端 API（`/api/:api`）。

## 协议端

需要运行一个 Milky 协议端实现，例如：

- [Lagrange.Milky](https://github.com/LagrangeDev/Lagrange.Core)（Lagrange.Core 仓库中的 `Lagrange.Milky` 项目）
- [Yogurt](https://acidify.ntqqrev.org/yogurt/start)
- [LuckyLilliaBot](https://github.com/LLOneBot/LLOneBot)

确认协议端 `POST /api/get_impl_info` 返回 `{"status": "ok", ...}` 即就绪。

## 配置

创建 `milky_config.json`（与 `config.json` 同理，已被 gitignore）：

```json
{
  "protocol": "Milky",
  "owner": [],
  "black_list": [],
  "silents": [],
  "connection": {
    "mode": "Milky",
    "host": "127.0.0.1",
    "port": 5005,
    "auth": ""
  },
  "log_level": "INFO",
  "log_use_nf": false,
  "uin": 0,
  "max_workers": 1,
  "others": {}
}
```

`host` / `port` 指向协议端的 HTTP 服务地址，`auth` 对应协议端的 `access_token`（未设置则为空）。字段说明见[配置文件](configuration.md)。

## 快速开始

```python
import asyncio
import hyperot

logger = hyperot.init("milky_config.json")

from hyperot import Client
from hyperot.events import GroupMessageEvent, PrivateMessageEvent

async def handler(event, actions):
    if str(event.message) == ".ping":
        await actions.send_msg("pong", group_id=event.group_id, user_id=event.user_id)

with Client() as cli:
    cli.subscribe(handler, [GroupMessageEvent, PrivateMessageEvent])
    asyncio.get_event_loop().run_until_complete(cli.run())
```

仓库内提供 `test_milky.py` 真机联调脚本：`uv run python test_milky.py`，覆盖事件接收、只读 API、发消息与撤回的全链路验证（在 QQ 上给机器人发送 `.e2e` 触发）。

## 事件映射

Milky 事件统一映射到框架的[事件模型](events.md)：

| Milky 事件 | 框架事件 |
|-----------|---------|
| `message_receive`（`friend` / `group` / `temp`） | `PrivateMessageEvent` / `GroupMessageEvent`（临时会话按私聊处理） |
| `bot_offline` | `BotOnLineEvent` |
| `message_recall` | `FriendRecallEvent` / `GroupRecallEvent` |
| `group_admin_change` | `GroupAdminEvent` |
| `group_essence_message_change` | `GroupEssenceEvent` |
| `group_member_increase` / `group_member_decrease` | `GroupMemberIncreaseEvent` / `GroupMemberDecreaseEvent` |
| `group_mute` | `GroupMuteEvent` |
| `group_whole_mute` | `GroupWholeMuteEvent` |
| `group_name_change` | `GroupNameChangeEvent` |
| `group_invitation` | `GroupInvitationEvent` |
| `group_file_upload` / `friend_file_upload` | `GroupFileUploadEvent` / `FriendFileUploadEvent` |
| `group_message_reaction` | `MessageReactionEvent` |
| `group_nudge` / `friend_nudge` | `NotifyEvent`（`sub_type = "poke"`） |
| `friend_request` | `FriendAddRequestEvent`（`flag` 为 `initiator_uid`） |
| `group_join_request` / `group_invited_join_request` | `GroupAddInviteEvent`（`flag` 编码为 `"{group_id}:{notification_seq}"`） |

其余事件类型（`peer_pin_change` 等）暂无对应事件类，会记录日志并跳过，不影响连接。

## 消息段

- **入站**：`text`、`mention`、`mention_all`、`face`、`reply`、`image`、`record`、`video`、`forward`、`market_face`、`light_app`、`xml`（`file` 与未知类型跳过）
- **出站**：`Text`、`At`（`qq="all"` 时转 `mention_all`）、`Reply`、`Faces`、`Image`、`Record`、`Video`、`Forward`（节点列表转 `outgoing_forward`）

## Actions

所有[标准 Actions 方法](actions.md)在 Milky 下可用：

- `send_msg` / `del_msg`：`message_id` 为 `场景 + 序号 + 会话` 的编码值，`del_msg` 自动解码并调用对应撤回 API
- `get_login_info` / `get_version_info`（映射 `get_impl_info`）/ `get_group_info` / `get_group_member_info` / `get_stranger_info`（映射 `get_user_profile`）等查询均可用
- `set_group_kick` / `set_group_ban` / `set_group_special_title` / `set_group_add_request` / `set_essence_msg` 等群管理可用
- `actions.custom` 可调用 Milky 独有 API（如 `set_group_whole_mute`、`set_group_member_card`、`send_group_nudge`），**返回响应 `data` 字典**（与 OneBot 返回 echo 不同）

## 已知限制

- `send_forward_msg`（无目标场景）与 `send_callback` 暂未支持，抛出 `NotImplementedError`；发送合并转发请使用 `send_group_forward_msg`
- 部分协议端（如特定版本 Lagrange.Milky）的 `recall_private_message` 存在协议端侧 bug（`GetC2CMessage` 拉取失败），私聊撤回可能失败，群撤回不受影响
