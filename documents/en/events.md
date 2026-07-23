# Events

All events inherit from `Event`. They are dispatched by the framework based on the `post_type` and sub-type in the OneBot JSON payload.

## Common Attributes

Every `Event` instance has:

| Attribute | Type | Description |
|-----------|------|-------------|
| `time` | `int` | Event timestamp |
| `self_id` | `int` | Bot QQ ID |
| `post_type` | `str` | Event category: `"message"`, `"notice"`, `"request"` |
| `user_id` | `int` | Trigger user QQ ID |
| `group_id` | `int` | Group ID (group events) |
| `is_owner` | `bool` | Whether sender is in the owner list |
| `blocked` | `bool` | Whether sender is blacklisted |
| `is_silent` | `bool` | Whether sender is in silent list |

## Message Events

| Event | Description | Extra Fields |
|--------|-------------|--------------|
| `MessageEvent` | Base class | `sub_type`, `message_id`, `message` (Message), `msg_str` |
| `PrivateMessageEvent` | Private message | `sender` (PrivateSender: `user_id`, `nickname`, `sex`, `age`) |
| `GroupMessageEvent` | Group message | `sender` (GroupSender: `user_id`, `nickname`, `sex`, `age`, `card`, `area`, `level`, `role`, `title`), `anonymous`, `is_mentioned` |

## Notice Events

| Event | Description | Extra Fields |
|--------|-------------|--------------|
| `GroupFileUploadEvent` | File uploaded to group | `file` |
| `GroupAdminEvent` | Admin changed | `sub_type` (`"set"` / `"unset"`) |
| `GroupMemberDecreaseEvent` | Member left/kicked | `sub_type`, `operator_id` |
| `GroupMemberIncreaseEvent` | Member joined | `sub_type`, `operator_id` |
| `GroupMuteEvent` | Member muted/unmuted | `sub_type` (`"ban"` / `"lift_ban"`), `operator_id`, `duration` |
| `FriendAddEvent` | Friend request received | — |
| `GroupRecallEvent` | Message recalled in group | `operator_id`, `message_id` |
| `FriendRecallEvent` | Message recalled by friend | `message_id` |
| `NotifyEvent` | Poke / lucky king / honor | `sub_type`, `target_id`, `honor_type` |
| `GroupEssenceEvent` | Essence message changed | `sub_type` (`"add"` / `"delete"`), `sender_id`, `operator_id`, `message_id` |
| `MessageReactionEvent` | Reaction added/removed | `message_id`, `sub_type`, `code`, `count` |
| `BotOnLineEvent` | Bot reconnected to QQ | `reason` |

## Request Events

| Event | Description | Extra Fields |
|--------|-------------|--------------|
| `RequestEvent` | Base class | `comment`, `flag` |
| `FriendAddRequestEvent` | Friend add request | — |
| `GroupAddInviteEvent` | Group invite request | `sub_type` |

## Framework Events

| Event | Description |
|--------|-------------|
| `HyperListenerStartNotify` | Listener started, provides `connection` reference |
| `HyperListenerStopNotify` | Listener stopped |
