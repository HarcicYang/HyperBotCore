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
| `GroupWholeMuteEvent` | Group-wide mute toggled | `sub_type` (`"mute"` / `"unmute"`), `operator_id` |
| `GroupNameChangeEvent` | Group name changed | `new_group_name`, `operator_id` |
| `GroupInvitationEvent` | Bot invited to join a group | `invitation_seq`, `initiator_id`, `source_group_id` |
| `FriendAddEvent` | Friend request received | — |
| `FriendFileUploadEvent` | File uploaded by friend | `file` (`{id, name, size, busid, hash}`) |
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
| `HyperListenerStartNotify` | Listener started, provides the `connection` reference |
| `HyperListenerStopNotify` | Listener stopped |

## Milky Event Mapping

When using the [Milky protocol](../en/configuration.md), protocol events are mapped onto the event model above:

| Milky event | Framework event |
|-------------|-----------------|
| `message_receive` (`friend` / `group` / `temp`) | `PrivateMessageEvent` / `GroupMessageEvent` (temp sessions are treated as private) |
| `bot_offline` | `BotOnLineEvent` |
| `message_recall` | `FriendRecallEvent` / `GroupRecallEvent` |
| `group_admin_change` | `GroupAdminEvent` |
| `group_essence_message_change` | `GroupEssenceEvent` |
| `group_member_increase` / `group_member_decrease` | `GroupMemberIncreaseEvent` / `GroupMemberDecreaseEvent` |
| `group_mute` / `group_whole_mute` | `GroupMuteEvent` / `GroupWholeMuteEvent` |
| `group_name_change` | `GroupNameChangeEvent` |
| `group_invitation` | `GroupInvitationEvent` |
| `group_file_upload` / `friend_file_upload` | `GroupFileUploadEvent` / `FriendFileUploadEvent` |
| `group_message_reaction` | `MessageReactionEvent` |
| `group_nudge` / `friend_nudge` | `NotifyEvent` (`sub_type = "poke"`) |
| `friend_request` | `FriendAddRequestEvent` (`flag` is `initiator_uid`) |
| `group_join_request` / `group_invited_join_request` | `GroupAddInviteEvent` (`flag` encoded as `"{group_id}:{notification_seq}"`) |

Other event types (e.g. `peer_pin_change`) have no corresponding event class yet; they are logged and skipped without breaking the connection.
