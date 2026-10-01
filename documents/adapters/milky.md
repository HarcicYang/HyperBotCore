# Milky 适配器

> 本文档只介绍 Milky 适配器。V2 公共能力见 [V2 文档](../v2/index.md)。

Milky 适配器让 V2 连接实现 Milky 1.3 的协议端。协议端提供两个端点：`/api/:api` 用于应用端调用 API，`/event` 用于向应用端推送事件。

## 安装

```shell
pip install hyper-bot hyperot-adapter-milky
```

安装后在 `appconfig.json` 中设置：

```json
{
  "active_adapter": "milky"
}
```

## 连接方式

Milky 适配器支持三种事件推送方式：

| 类型 | 用途 |
| --- | --- |
| `WebSocket` | 框架主动连接协议端的 `/event` WebSocket。 |
| `SSE` | 框架以 Server-Sent Events 订阅协议端的 `/event`。 |
| `WebHook` | 框架监听 HTTP 地址，协议端把事件推送过来。 |

三种方式都通过 HTTP 调用 `/api/:api`，因此 API 调用行为完全一致。最常见的是 WebSocket。

## WebSocket

```json
{
  "active_adapter": "milky",
  "adapter_config": {
    "connections": [
      {
        "type": "WebSocket",
        "url": "ws://127.0.0.1:5005"
      }
    ]
  }
}
```

`url` 是协议端地址，不要带 `/event`。API 地址默认由 `url` 推导（`ws://` 推导为 `http://`）；如果 API 在别的地址，用 `api_url` 单独指定。

## SSE

```json
{
  "active_adapter": "milky",
  "adapter_config": {
    "connections": [
      {
        "type": "SSE",
        "url": "http://127.0.0.1:5005",
        "reconnect_delay": 3.0
      }
    ]
  }
}
```

SSE 断开后适配器会按 `reconnect_delay` 秒重连。

## WebHook

```json
{
  "active_adapter": "milky",
  "adapter_config": {
    "connections": [
      {
        "type": "WebHook",
        "api_url": "http://127.0.0.1:5005",
        "host": "127.0.0.1",
        "port": 6702,
        "endpoint": "/milky"
      }
    ]
  }
}
```

然后在协议端把事件推送地址设置为 `http://127.0.0.1:6702/milky`。WebHook 方式必须提供 `api_url`，因为协议端地址无法从框架的监听地址推导。

## 鉴权

`access_token` 是连接级配置：

- WebSocket 和 SSE 会发送 `Authorization: Bearer <access_token>`。
- WebHook 校验协议端推送时携带的同一个请求头，缺失或不匹配时返回 401。

协议端开启了鉴权而框架没有配置 token 时，连接或 API 调用会失败。

## 消息格式

Milky 消息段会转换成 V2 公共消息段：

| Milky 消息段 | V2 消息段 |
| --- | --- |
| `text` | `Text` |
| `mention` | `Mention` |
| `mention_all` | `MentionAll` |
| `face` | `Face` |
| `reply` | `Quote`（含被引用消息内容） |
| `image` | `Image`（保留 `resource_id`、`sub_type`） |
| `record` | `Audio`（保留 `resource_id`） |
| `video` | `Video`（保留 `resource_id`） |
| `file` | `File`（保留 `file_hash`） |
| `forward` | `Forward` |
| `market_face`、`light_app`、`xml`、`markdown` | 适配器自定义消息段 |

发送消息时只支持协议端定义的发送消息段。收到的 `file`、`forward`（按 ID）、`market_face`、`xml`、`markdown` 不能直接回发，需要改用群文件上传、转发节点等对应 API。

Milky 1.2 要求应用端把未知消息段转换为文本，因此适配器遇到不认识的段时会返回 `[不支持的消息段: <type>]`。

## 消息 ID

Milky 用「场景 + 会话 + 序列号」定位消息，没有全局消息 ID。适配器把它编码成字符串：

```text
group:12345:678     群消息（场景: 群号: 序列号）
friend:10001:678    好友消息
temp:12345:678      临时会话消息
```

事件里的 `message_id`、发送结果的 `message_id` 都是这个格式，撤回、引用、表情回应和精华消息都基于它，不需要额外上下文。临时会话消息按私聊处理，`client.api` 的会话 ID 是发起会话的成员 QQ 号。

## 支持的 API

大部分常用能力已经封装为 `client.api`。公共 API 见 [V2 API](../v2/api.md)。

### 消息

```python
await client.api.group(group_id).send("hello")
await client.api.user(user_id).send("hello")
await client.api.message(message_id).recall()
await client.api.message(message_id).fetch()
await client.api.message(message_id).react("👍")
```

### 群管理

```python
await client.api.group(group_id).set_name("新群名")
await client.api.group(group_id).mute_all()
await client.api.group(group_id).unmute_all()
await client.api.group(group_id).leave()

member = client.api.group(group_id).member(user_id)
await member.kick(reject_add_request=True)
await member.mute(600)
await member.unmute()
await member.set_card("新名片")
await member.set_title("新头衔")
```

### 查询

```python
await client.api.bot.profile()
await client.api.bot.version()

await client.api.user(user_id).profile()
await client.api.group(group_id).profile()
await client.api.group(group_id).members()
```

`bot.status()` 在 Milky 下没有对应接口，返回本地状态。

### 请求

```python
await client.api.friend_request(request_id).approve()
await client.api.friend_request(request_id).reject("暂时不加")

await client.api.group_request(request_id).approve()
await client.api.group_request(request_id).reject("不通过")
```

好友请求的 `request_id` 是请求发起者的 UID；群请求的 `request_id` 形如 `group_request:<群号>:<通知序列号>`。

他人邀请机器人入群使用单独的邀请 API：

```python
await client.api.invitation(request_id).accept()
await client.api.invitation(request_id).reject("不加了")
```

### 表情回应

```python
await client.api.group(group_id).reaction(message_id, "👍")
```

`reaction` 传纯数字时按 QQ 系统表情发送，其他内容按 Emoji 发送。

### 文件

```python
file_url = await client.api.file(file_id).group_url(group_id)
file_url = await client.api.file(file_id).private_url(user_id, file_hash="...")
files = await client.api.group(group_id).files("/")
await client.api.group(group_id).upload_file("file:///tmp/a.zip", name="a.zip")
```

私聊文件下载链接需要 `file_hash`。文件来自事件时，适配器会记住它的场景和哈希，`info()` 和 `download()` 可以直接使用；跨进程重启后请改用 `group_url()` 或 `private_url()`。

### 其他扩展

```python
await client.api.user(user_id).send_like(count=10)
await client.api.bot.cookies("example.com")
await client.api.bot.csrf_token()
```

如果某个 Milky API 还没有专门方法，可以使用：

```python
result = await client.api.raw("get_peer_pins", {})
```

## 支持的事件

Milky 适配器会把协议事件转换成 V2 公共事件：

- 好友消息、群消息、临时会话消息、消息撤回。
- 群管理员变更、成员加入、成员离开、群解散、群名称变更。
- 群禁言、全员禁言、群精华消息变更、群消息表情回应。
- 群文件上传、好友文件上传。
- 好友戳一戳、群戳一戳、会话置顶变更。
- 好友请求、入群请求、邀请他人入群请求、他人邀请自身入群。
- 机器人离线。

未知事件类型会被忽略并打印警告日志，符合 Milky 1.2 对应用端的要求。

## 常见问题

### 连接被拒绝

先确认 Milky 实现已经在监听配置里的地址，再启动机器人。连接失败时框架会按 `runtime.reconnect_max_attempts` 重试，日志形如：

```text
Warning  adapter connection failed: Milky websocket connection to ws://127.0.0.1:5005/event failed: connection refused (check that the Milky end is running and listening on 127.0.0.1:5005); retrying in 1.0s (attempt 1/5)
```

重试用尽后 `run()` 退出并抛出 `AdapterConnectionError`。希望一直等到协议端上线，把 `runtime.reconnect_max_attempts` 设为 `null`。

### WebHook 端口启动失败

启动前框架会先确认地址可以监听，端口被占用时日志会直接指出地址：

```text
Error  Milky listener on 127.0.0.1:6700 failed: address already in use (another process is already listening on 127.0.0.1:6700)
```

换一个 `port`，或者先停掉占用该端口的进程。这类失败同样会按 `runtime.reconnect_max_attempts` 重试，不会直接让进程退出。

### 连接成功但收不到消息

确认协议端开放了 `/event`，并且事件推送方式与配置一致。WebHook 方式需要确认协议端推送地址可达。

### API 返回 401

通常是 `access_token` 不一致。确认协议端和框架连接配置里的 token 相同。

### 撤回或表情回应失败

确认使用的 `message_id` 来自本框架的事件或发送结果。Milky 的撤回和表情回应只支持群消息表情回应，私聊消息无法回应。

### 收到不支持的消息段

协议端版本比适配器新时会增加消息段。适配器会把它转换为 `[不支持的消息段: <type>]`，可以先升级适配器，再用 `client.api.raw()` 直接调用新 API。
