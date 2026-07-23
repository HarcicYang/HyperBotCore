# 事件系统

所有事件继承自 `Event`，框架根据 OneBot JSON 中的 `post_type` 和子类型自动分发。

## 通用属性

每个 `Event` 实例都包含：

| 属性 | 类型 | 说明 |
|-----------|------|------|
| `time` | `int` | 事件时间戳 |
| `self_id` | `int` | 机器人 QQ 号 |
| `post_type` | `str` | 事件大类：`"message"`、`"notice"`、`"request"` |
| `user_id` | `int` | 触发用户 QQ 号 |
| `group_id` | `int` | 群号（群事件） |
| `is_owner` | `bool` | 发送者是否在主人列表中 |
| `blocked` | `bool` | 发送者是否被屏蔽 |
| `is_silent` | `bool` | 发送者是否在静默列表中 |

## 消息事件

| 事件 | 说明 | 特有属性 |
|--------|------|----------|
| `MessageEvent` | 基类 | `sub_type`、`message_id`、`message` (Message)、`msg_str` |
| `PrivateMessageEvent` | 私聊消息 | `sender` (PrivateSender: `user_id`、`nickname`、`sex`、`age`) |
| `GroupMessageEvent` | 群聊消息 | `sender` (GroupSender: `user_id`、`nickname`、`sex`、`age`、`card`、`area`、`level`、`role`、`title`)、`anonymous`、`is_mentioned` |

## 通知事件

| 事件 | 说明 | 特有属性 |
|--------|------|----------|
| `GroupFileUploadEvent` | 群文件上传 | `file` |
| `GroupAdminEvent` | 管理员变更 | `sub_type`（`"set"` / `"unset"`） |
| `GroupMemberDecreaseEvent` | 群成员减少 | `sub_type`、`operator_id` |
| `GroupMemberIncreaseEvent` | 群成员增加 | `sub_type`、`operator_id` |
| `GroupMuteEvent` | 禁言/解除禁言 | `sub_type`（`"ban"` / `"lift_ban"`）、`operator_id`、`duration` |
| `FriendAddEvent` | 好友添加 | — |
| `GroupRecallEvent` | 群消息撤回 | `operator_id`、`message_id` |
| `FriendRecallEvent` | 好友消息撤回 | `message_id` |
| `NotifyEvent` | 戳一戳/龙王/群荣誉 | `sub_type`、`target_id`、`honor_type` |
| `GroupEssenceEvent` | 精华消息变更 | `sub_type`（`"add"` / `"delete"`）、`sender_id`、`operator_id`、`message_id` |
| `MessageReactionEvent` | 表情回应 | `message_id`、`sub_type`、`code`、`count` |
| `BotOnLineEvent` | Bot 重新上线 | `reason` |

## 请求事件

| 事件 | 说明 | 特有属性 |
|--------|------|----------|
| `RequestEvent` | 基类 | `comment`、`flag` |
| `FriendAddRequestEvent` | 好友添加请求 | — |
| `GroupAddInviteEvent` | 群邀请请求 | `sub_type` |

## 框架事件

| 事件 | 说明 |
|--------|------|
| `HyperListenerStartNotify` | 监听器启动，提供 `connection` 引用 |
| `HyperListenerStopNotify` | 监听器停止 |
