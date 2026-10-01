# OneBot v11 适配器

> 本文档只介绍 OneBot 适配器。V2 公共能力见 [V2 文档](../v2/index.md)。

OneBot 适配器让 V2 可以连接 OneBot v11 实现，例如 EulerOneBot、Lagrange.OneBot、NapCat 和 LLOneBot。

## 安装

```shell
pip install hyper-bot hyperot-adapter-onebot
```

安装后在 `appconfig.json` 中设置：

```json
{
  "active_adapter": "onebot"
}
```

## 连接方式

OneBot 适配器支持四种连接方式：

| 类型 | 用途 |
| --- | --- |
| `ForwardWebSocket` | 框架主动连接 OneBot 实现的 WebSocket。 |
| `ReverseWebSocket` | 框架监听端口，由 OneBot 实现反向连接。 |
| `HTTP` | 框架通过 HTTP 调用 OneBot API。 |
| `HTTPPost` | 框架监听 HTTP 地址，接收 OneBot 推送的事件。 |

最常见的是正向 WebSocket。

## 正向 WebSocket

```json
{
  "active_adapter": "onebot",
  "adapter_config": {
    "connections": [
      {
        "type": "ForwardWebSocket",
        "url": "ws://127.0.0.1:5004",
        "access_token": ""
      }
    ]
  }
}
```

确认 OneBot 实现已经开放对应地址，再启动机器人。

## 反向 WebSocket

```json
{
  "active_adapter": "onebot",
  "adapter_config": {
    "connections": [
      {
        "type": "ReverseWebSocket",
        "host": "0.0.0.0",
        "port": 6700,
        "api_path": "/api",
        "event_path": "/event",
        "access_token": ""
      }
    ]
  }
}
```

OneBot 实现可以分别连接 API 和 Event，也可以使用 Universal 连接。Universal 会在同一条连接上同时处理 API 调用和事件推送。

## HTTP 与 HTTPPost

如果希望 API 和事件分开：

```json
{
  "active_adapter": "onebot",
  "adapter_config": {
    "connections": [
      {
        "type": "HTTP",
        "url": "http://127.0.0.1:5700",
        "access_token": ""
      },
      {
        "type": "HTTPPost",
        "host": "127.0.0.1",
        "port": 6701,
        "endpoint": "/onebot",
        "secret": ""
      }
    ]
  }
}
```

然后在 OneBot 实现里把事件上报地址设置为 `http://127.0.0.1:6701/onebot`。

HTTPPost 的“快速操作”暂不支持。需要回复、撤回或禁言时，在事件处理器里直接调用 `client.api`。

## 鉴权

`access_token` 是连接级配置，不是顶层配置。

- HTTP 和正向 WebSocket 会发送 `Authorization: Bearer <access_token>`。
- 反向 WebSocket 会校验 OneBot 实现传来的 token。
- HTTPPost 使用 `secret` 校验 `X-Signature`。

如果 OneBot 实现开启了鉴权，而框架配置里没有对应 token，连接或 API 调用会失败。

## 消息格式

OneBot 适配器只支持数组格式的消息。也就是说，事件里的 `message` 应该长这样：

```json
[
  {"type": "text", "data": {"text": "你好"}},
  {"type": "image", "data": {"file": "https://example.com/a.png"}}
]
```

如果协议端发送的是字符串消息，适配器会拒绝该事件，不会尝试解析字符串格式。EulerOneBot 默认发送数组格式，可以直接使用。

## 支持的 API

大部分常用能力已经封装为 `client.api`，不需要记 OneBot action 名。公共 API 见 [V2 API](../v2/api.md)。

### 消息

```python
await client.api.group(group_id).send("hello")
await client.api.user(user_id).send("hello")
await client.api.message(message_id).recall()
await client.api.message(message_id).fetch()
```

### 群管理

```python
await client.api.group(group_id).set_name("新群名")
await client.api.group(group_id).mute_all()
await client.api.group(group_id).unmute_all()
await client.api.group(group_id).leave()

member = client.api.group(group_id).member(user_id)
await member.kick()
await member.mute(600)
await member.unmute()
await member.set_card("新名片")
await member.set_title("新头衔")
```

### 查询

```python
await client.api.bot.profile()
await client.api.bot.status()
await client.api.bot.version()

await client.api.user(user_id).profile()
await client.api.group(group_id).profile()
await client.api.group(group_id).members()
```

### 请求

```python
await client.api.friend_request(request_id).approve()
await client.api.friend_request(request_id).reject("暂时不加")

await client.api.group_request(request_id).approve()
await client.api.group_request(request_id).reject("不通过")
```

### OneBot 扩展能力

```python
await client.api.user(user_id).send_like(times=10)
await client.api.group(group_id).reaction(message_id, "👍")
await client.api.bot.cookies("example.com")
await client.api.bot.csrf_token()
```

文件 URL：

```python
await client.api.file(file_id).group_url(group_id)
await client.api.file(file_id).private_url(user_id, file_hash="...")
```

如果某个 OneBot API 还没有专门方法，可以使用：

```python
result = await client.api.raw("some_action", {"key": "value"})
```

## 支持的事件

OneBot 适配器会把 OneBot 事件转换成 V2 公共事件。常见事件包括：

- 私聊消息、群消息。
- 消息撤回、表情回应。
- 群文件上传。
- 群管理员、成员加入、成员离开、禁言、群名变化。
- 好友添加、好友请求、群请求和群邀请。
- 戳一戳。
- 生命周期和心跳。

事件字段见[事件](../v2/events.md)。心跳不会打印日志，其他事件会按照统一格式输出。

## Reaction 说明

QQ 平台只支持群消息表情回应。推荐通过群 API 调用：

```python
await client.api.group(group_id).reaction(message_id, "👍")
```

消息 API 也支持常见场景：

```python
await client.api.message(message_id).react("👍")
await client.api.message(message_id).unreact("👍")
```

如果消息上下文不可用，消息 API 会报错。此时改用群 API 更明确。

## 文件说明

OneBot 没有通用的“获取任意文件信息”和“下载任意文件”接口，因此：

```python
await client.api.file(file_id).info()
await client.api.file(file_id).download()
```

在 OneBot 下不可用。请使用 `group_url()` 或 `private_url()`。

## 常见问题

### 连接成功但收不到消息

检查 OneBot 实现是否真的把事件推送到了当前连接。正向 WebSocket 通常需要协议端启用 WebSocket 服务；HTTPPost 需要确认上报地址。

### API 返回 401 或 403

通常是 `access_token` 不一致。确认 OneBot 实现和框架连接配置里的 token 相同。

### 反向 WebSocket 连不上

确认 OneBot 实现连接的是框架监听的 `host` 和 `port`。如果使用 Universal，确认协议端发送了正确的连接角色。

### 收到字符串消息事件被拒绝

当前适配器只支持数组消息。把协议端的事件消息格式设置为数组格式。

### 某些事件没有出现

先确认 OneBot 实现本身是否支持该事件。框架只会转换协议端实际发送过来的事件。
