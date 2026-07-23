# Actions（API 操作）

每个 handler 的第二个参数是 `actions` 对象，提供全部 OneBot v11 API 方法。

## 消息相关

| 方法                                          | 返回                       | 说明             |
|---------------------------------------------|--------------------------|----------------|
| `send_msg(message, group_id?, user_id?)`    | `Ret[MsgSendRsp]`        | 发送消息，自动判断群聊/私聊 |
| `send_group_msg(message, group_id)`         | `Ret[MsgSendRsp]`        | 发送群消息          |
| `send_private_msg(message, user_id)`        | `Ret[MsgSendRsp]`        | 发送私聊消息         |
| `del_msg(message_id)`                       | `None`                   | 撤回消息           |
| `send_forward_msg(message)`                 | `Ret[SendForwardRsp]`    | 发送合并转发         |
| `send_group_forward_msg(group_id, message)` | `Ret[SendGrpForwardRsp]` | 发送群合并转发        |
| `get_forward_msg(sid)`                      | `Ret[Message]`           | 获取合并转发消息       |
| `get_msg(msg_id)`                           | `Ret[GetMsgRsp]`         | 获取消息详情         |

`send_msg` 自动判断目标：传 `group_id` 发群聊，传 `user_id` 发私聊。两者都不传会抛出 `ArgsInvalidError`。

`message` 参数接受 `str`（自动包装为 `Text`）或 `Message` 对象。

## 群管理

| 方法                                                       | 返回     | 说明       |
|----------------------------------------------------------|--------|----------|
| `set_group_kick(group_id, user_id)`                      | `None` | 踢出成员     |
| `set_group_ban(group_id, user_id, duration=60)`          | `None` | 禁言（单位：秒） |
| `set_group_special_title(group_id, user_id, title)`      | `None` | 设置群头衔    |
| `set_group_add_request(flag, sub_type, approve, reason)` | `None` | 处理加群请求   |
| `set_essence_msg(message_id)`                            | `None` | 设置精华消息   |

## 信息查询

| 方法                                         | 返回                      | 说明             |
|--------------------------------------------|-------------------------|----------------|
| `get_login_info()`                         | `Ret[GetLoginInfoRsp]`  | 获取 Bot 登录信息    |
| `get_version_info()`                       | `Ret[GetVerInfoRsp]`    | 获取 OneBot 实现版本 |
| `get_status()`                             | `Ret`                   | 获取在线状态         |
| `get_stranger_info(user_id)`               | `Ret[GetStrInfoRsp]`    | 获取陌生人信息        |
| `get_group_member_info(group_id, user_id)` | `Ret[GetGrpMemInfoRsp]` | 获取群成员信息        |
| `get_group_info(group_id)`                 | `Ret[GetGrpInfoRsp]`    | 获取群信息          |

## 回调

| 方法                                      | 返回     | 说明               |
|-----------------------------------------|--------|------------------|
| `send_callback(group_id, bot_id, data)` | `None` | 发送群 bot 回调（键盘按钮） |

## 自定义 API 调用

对于尚未封装的 OneBot API：

```python
await actions.custom.send_like(user_id=123456, times=10)
```

方法名即为 OneBot `action` 字段，关键字参数即为 `params` 字典。返回 `str` 类型的 echo ID。

## Ret\<T\>

所有 API 调用返回泛型 `Ret[T]`：

```python
res = await actions.send_msg("hello", group_id=123456)

res.status  # str: "ok" / "failed"
res.ret_code  # int: 返回码
res.data  # T: 类型化响应数据
res.echo  # str: 请求 echo ID
res.raw  # dict: 原始 JSON
```

### 响应数据类型

| 类型                  | 属性                                                                                                                                                               |
|---------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `MsgSendRsp`        | `message_id: int`                                                                                                                                                |
| `GetLoginInfoRsp`   | `user_id: int`、`nickname: str`                                                                                                                                   |
| `GetVerInfoRsp`     | `app_name: str`、`app_version: str`、`protocol_version: str`                                                                                                       |
| `GetStrInfoRsp`     | `user_id: int`、`nickname: str`、`sex: str`、`age: int`                                                                                                             |
| `GetGrpMemInfoRsp`  | `group_id`、`user_id`、`nickname`、`card`、`sex`、`age`、`area`、`join_time`、`last_sent_time`、`level`、`role`、`unfriendly`、`title`、`title_expire_time`、`card_changeable` |
| `GetGrpInfoRsp`     | `group_id: int`、`group_name: str`、`member_count: int`、`max_member_count: int`                                                                                    |
| `GetMsgRsp`         | `time`、`message_type`、`message_id`、`real_id`、`sender`、`message` (Message)                                                                                        |
| `SendForwardRsp`    | `res_id: str`                                                                                                                                                    |
| `SendGrpForwardRsp` | `message_id: int`、`forward_id: str`                                                                                                                              |
