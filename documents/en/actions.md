# Actions (API)

Every handler receives an `actions` object as its second argument. It provides all OneBot v11 API methods.

## Messaging

| Method | Returns | Description |
|--------|---------|-------------|
| `send_msg(message, group_id?, user_id?)` | `Ret[MsgSendRsp]` | Send message to group or user |
| `send_group_msg(message, group_id)` | `Ret[MsgSendRsp]` | Send group message |
| `send_private_msg(message, user_id)` | `Ret[MsgSendRsp]` | Send private message |
| `del_msg(message_id)` | `None` | Recall/delete message |
| `send_forward_msg(message)` | `Ret[SendForwardRsp]` | Send forward message |
| `send_group_forward_msg(group_id, message)` | `Ret[SendGrpForwardRsp]` | Send group forward message |
| `get_forward_msg(sid)` | `Ret[Message]` | Get forward message by ID |
| `get_msg(msg_id)` | `Ret[GetMsgRsp]` | Get message detail |

`send_msg` auto-detects target: pass `group_id` for groups, `user_id` for private chats. Passing neither raises `ArgsInvalidError`.

The `message` parameter accepts either a `str` (auto-wrapped as `Text`) or a `Message` object.

## Group Management

| Method | Returns | Description |
|--------|---------|-------------|
| `set_group_kick(group_id, user_id)` | `None` | Kick member |
| `set_group_ban(group_id, user_id, duration=60)` | `None` | Ban member (duration in seconds) |
| `set_group_special_title(group_id, user_id, title)` | `None` | Set special title |
| `set_group_add_request(flag, sub_type, approve, reason)` | `None` | Handle join request |
| `set_essence_msg(message_id)` | `None` | Set essence message |

## Info Queries

| Method | Returns | Description |
|--------|---------|-------------|
| `get_login_info()` | `Ret[GetLoginInfoRsp]` | Get bot login info |
| `get_version_info()` | `Ret[GetVerInfoRsp]` | Get OneBot impl version |
| `get_status()` | `Ret` | Get online status |
| `get_stranger_info(user_id)` | `Ret[GetStrInfoRsp]` | Get stranger info |
| `get_group_member_info(group_id, user_id)` | `Ret[GetGrpMemInfoRsp]` | Get member info |
| `get_group_info(group_id)` | `Ret[GetGrpInfoRsp]` | Get group info |

## Callback

| Method | Returns | Description |
|--------|---------|-------------|
| `send_callback(group_id, bot_id, data)` | `None` | Send group bot callback (keyboard) |

## Custom API Calls

For OneBot APIs not yet wrapped:

```python
await actions.custom.send_like(user_id=123456, times=10)
```

The method name becomes the OneBot `action` field, and keyword arguments become the `params` dict. Returns a `str` echo ID.

## Ret\<T\>

All API responses are wrapped in a generic `Ret[T]`:

```python
res = await actions.send_msg("hello", group_id=123456)

res.status    # str: "ok" / "failed"
res.ret_code  # int: return code
res.data      # T: typed response data
res.echo      # str: request echo ID
res.raw       # dict: raw JSON
```

### Response Data Types

| Type | Attributes |
|------|------------|
| `MsgSendRsp` | `message_id: int` |
| `GetLoginInfoRsp` | `user_id: int`, `nickname: str` |
| `GetVerInfoRsp` | `app_name: str`, `app_version: str`, `protocol_version: str` |
| `GetStrInfoRsp` | `user_id: int`, `nickname: str`, `sex: str`, `age: int` |
| `GetGrpMemInfoRsp` | `group_id`, `user_id`, `nickname`, `card`, `sex`, `age`, `area`, `join_time`, `last_sent_time`, `level`, `role`, `unfriendly`, `title`, `title_expire_time`, `card_changeable` |
| `GetGrpInfoRsp` | `group_id: int`, `group_name: str`, `member_count: int`, `max_member_count: int` |
| `GetMsgRsp` | `time`, `message_type`, `message_id`, `real_id`, `sender`, `message` (Message) |
| `SendForwardRsp` | `res_id: str` |
| `SendGrpForwardRsp` | `message_id: int`, `forward_id: str` |
