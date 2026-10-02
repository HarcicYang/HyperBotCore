# Satori 适配器

> 本文档只介绍 Satori 适配器。V2 公共能力见 [V2 文档](../v2/index.md)。

Satori 适配器让 V2 连接任意实现 [Satori 协议](https://github.com/satorijs/docs)的服务端。协议端提供两类接口：HTTP API（`POST /v1/{resource}.{method}`）和事件服务（WebSocket `/v1/events` 或 WebHook 推送）。

## 安装

```shell
pip install hyper-bot hyperot-adapter-satori
```

安装后在 `appconfig.json` 中设置：

```json
{
  "active_adapter": "satori"
}
```

## 连接方式

Satori 适配器支持两种事件推送方式：

| 类型 | 用途 |
| --- | --- |
| `WebSocket` | 框架连接协议端的 `/v1/events`，发送 `IDENTIFY` 鉴权，每 10 秒发送一次 `PING`。 |
| `WebHook` | 框架监听 HTTP 地址，协议端把事件推送过来。 |

两种方式都通过 HTTP 调用 API，因此 API 行为完全一致。最常见的是 WebSocket。

## WebSocket

```json
{
  "active_adapter": "satori",
  "adapter_config": {
    "connections": [
      {
        "type": "WebSocket",
        "url": "ws://127.0.0.1:5140"
      }
    ]
  }
}
```

`url` 是协议端地址，不要带 `/v1/events`。API 地址默认由 `url` 推导（`ws://` 推导为 `http://`）；如果 API 在别的地址，用 `api_url` 单独指定。

WebSocket 连接建立后框架会立刻发送 `IDENTIFY`（携带 `access_token`），之后每 10 秒发送一次 `PING`。`READY` 信令里的 `logins` 会注册为当前可用账号，连接断开时框架按 `runtime.reconnect_max_attempts` 重试。

## WebHook

```json
{
  "active_adapter": "satori",
  "adapter_config": {
    "connections": [
      {
        "type": "WebHook",
        "api_url": "http://127.0.0.1:5140",
        "host": "127.0.0.1",
        "port": 5141,
        "endpoint": "/satori",
        "token": "app-token"
      }
    ]
  }
}
```

`api_url` 是协议端 API 地址；`host`/`port`/`endpoint` 是框架监听的推送地址。`token` 是反向鉴权令牌，框架会要求协议端在 `Authorization: Bearer <token>` 中带上它。启动时框架会调用 `/v1/meta` 获取登录信息，并在 `register_webhook` 为 `true`（默认）时调用 `meta/webhook.create` 注册推送地址；停机时会调用 `meta/webhook.delete` 把它删掉，避免协议端继续往已经不存在的地址推送。

## 鉴权

`access_token` 是连接级配置。WebSocket 握手和 HTTP API 都会发送 `Authorization: Bearer <access_token>`；WebHook 方式下框架另用 `token` 校验协议端推送过来的请求。

## 登录号

Satori 的每个 API 调用都要带上 `Satori-Platform` 和 `Satori-User-ID`，用来区分连接上的多个登录号。默认使用第一个在线登录号；连接配置里的 `platform` 和 `user_id` 可以指定用哪一个：

```json
{
  "type": "WebSocket",
  "url": "ws://127.0.0.1:5140",
  "platform": "qq",
  "user_id": "10000"
}
```

## 消息格式

Satori 的消息内容是一段类 XHTML 的消息元素，而不是消息段数组。适配器自带解析器和序列化器，元素与 V2 消息段的对应关系如下：

| 消息元素 | V2 消息段 |
| --- | --- |
| `<at id=".."/>`、`<at type="all"/>` | `Mention`、`MentionAll` |
| `<emoji id=".."/>` | `Face` |
| `<img src=".."/>` | `Image` |
| `<audio src=".."/>` | `Audio` |
| `<video src=".."/>` | `Video` |
| `<file src=".."/>` | `File` |
| `<quote id="..">` | `Quote`（子元素解析为被引用的消息） |
| `<message id=".." forward/>` | `Forward` |
| `<message><author/>文字</message>` | `ForwardNode` |
| `<b> <i> <u> <s> <code>` 等修饰元素 | 保留其中内容 |
| `<br/>`、`<p>` | 文本换行 / 段落内容 |
| 平台原生元素（如 `<kook:card/>`） | `UnknownSegment`，原样保留 |

解析规则与协议规范和官方 SDK 使用的 `@cordisjs/element` 一致：注释会被丢弃，未配对的结束标签会被忽略，文本前后包含换行的连续空白会被去掉，属性名会转换成驼峰形式。

发送时 `Markdown` 段按纯文本发送——Satori 标准元素里没有富文本容器。

## 支持的 API

大部分常用能力已经封装为 `client.api`。公共 API 见 [V2 API](../v2/api.md)。

### 消息

```python
await client.api.group(group_id).send("hello")
await client.api.channel(channel_id).send("hello")
await client.api.user(user_id).send("hello")
await client.api.message(message_id).recall()
await client.api.message(message_id).fetch()
await client.api.message(message_id).react("thumbsup")
```

`group()` 用群组 ID，`channel()` 用频道 ID，两者都会落到 `message.create`。私聊发送会先调用 `user.channel.create` 拿到私聊频道。

### 群管理

```python
await client.api.group(group_id).mute_all()
await client.api.group(group_id).unmute_all()

member = client.api.group(group_id).member(user_id)
await member.kick()
await member.mute(600)
await member.unmute()
await member.set_role(MemberRole.ADMIN)
await member.set_role_id("role-1")
```

`set_role()` 会按角色名在 `guild.role.list` 的结果里匹配（群主/管理员/成员），需要精确控制时用 `set_role_id()`。

### 查询

```python
await client.api.bot.profile()

await client.api.user(user_id).profile()
await client.api.group(group_id).profile()
await client.api.group(group_id).members()
await client.api.group(group_id).channels()
await client.api.group(group_id).roles()
await client.api.channel(channel_id).messages()
```

列表类 API 会自动跟随 `next` 分页令牌。

### 请求

```python
await client.api.friend_request(request_id).approve()
await client.api.friend_request(request_id).reject("暂时不加")

await client.api.group_request(request_id).approve()
await client.api.group_request(request_id).reject("不通过")
```

好友申请、加群申请和入群邀请在协议里都叫 `message_id`，适配器在 request id 里编码了类型，`approve()`/`reject()` 会自动选择 `friend.approve`、`guild.member.approve` 或 `guild.approve`。

### 文件

```python
url = await client.api.file(file_id).download()
remote = await client.api.upload({"pic": "./a.png"})
```

`download()` 会按协议的资源链接规则处理：`internal:` 链接和 `proxy_urls` 里列出的链接会走协议端的 `/v1/proxy` 路由，普通公网链接直接返回。`upload()` 调用 `upload.create` 上传本地文件或 URL，返回可以直接写进 `<img src>` 的地址。

### 平台原生接口

协议没有标准化的能力可以走内部接口：

```python
result = await client.api.raw("guild.member.list", {"guild_id": "1"})
result = await client.api.raw("internal/channels/123", {})
```

`raw()` 的路由会原样拼到 `/v1/` 后面，因此标准 API 和 `/v1/internal/` 下的平台原生 API 都能调用。

## 支持的事件

协议事件与 V2 事件的对应关系：

| 协议事件 | V2 事件 |
| --- | --- |
| `message-created` | `MessageReceivedEvent` |
| `message-updated` | `MessageReceivedEvent` 的子类事件 |
| `message-deleted` | `MessageRecalledEvent` |
| `reaction-added` / `reaction-removed` | `MessageReactionChangedEvent` |
| `guild-member-added` / `-removed` | `MemberJoinedEvent` / `MemberLeftEvent` |
| `guild-member-updated` | `MemberRoleChangedEvent` |
| `guild-member-request` | `GroupJoinRequestedEvent` |
| `guild-request` | `GroupInvitationReceivedEvent` |
| `friend-request` | `FriendRequestedEvent` |
| `guild-updated` | `GroupNameChangedEvent` |
| `login-added` / `login-removed` / `login-updated` | `BotOnlineEvent` / `BotOfflineEvent` / 登录变更事件 |
| `guild-added` / `guild-removed`、`channel-*`、`guild-role-*`、`guild-emoji-*`、`interaction/*`、`internal` | 适配器自定义事件 |

未知事件类型会被忽略并打印警告日志，符合协议对应用端的要求。

## 场景与频道

Satori 用「群组 + 频道」描述会话，V2 用场景描述。适配器的取舍是：

- 群组里的文本频道：`SceneType.GUILD`，`scene_id` 是频道 ID，事件上带 `guild_id`。
- 私聊频道：`SceneType.USER`，`scene_id` 是对端用户 ID。
- 群组层面的事件（成员、角色、申请）：`SceneType.GROUP`，`scene_id` 是群组 ID。

给群组发消息时，适配器会先用事件里学到的频道，学不到时调用 `channel.list` 取第一个文本频道。

## 消息 ID

Satori 的消息 ID 只在频道内唯一：协议里 `message.get`、`message.delete`、`message.update` 和 `reaction.*` 都必须同时传 `channel_id` 和 `message_id`。V2 的消息动作只带一个字符串 ID，所以适配器把两者打包成 `频道ID:消息ID`：

- 事件的 `message_id` 和发送结果的 `message_id` 都是这个形式，可以直接传给 `client.api.message()`。
- 消息内容里的引用与转发（`<quote id>`、`<message id forward>`）在解析时会用所在频道补全成同样的形式，发送时再还原成协议里的裸消息 ID，符合协议元素只带消息 ID 的定义。
- 从协议端直接拿到的裸消息 ID 不能直接使用，需要自己带上频道，例如 `client.api.raw("message.delete", {"channel_id": ..., "message_id": ...})`。

冒号是适配器约定，和 Milky 适配器一样；如果某个平台的原始消息 ID 里本来就含冒号，打包结果会有歧义。

## 协议差异

- 禁言时长：协议用毫秒，V2 动作用秒，适配器负责换算。
- 全员禁言：协议只有实验性的 `channel.mute`，需要一个时长；适配器发送 30 天表示开启，0 表示解除。
- 不支持的能力：Satori 没有戳一戳、设置群名、设置名片/头衔、精华消息、退群、点赞、Cookie、CSRF Token 的标准 API，调用这些 API 会抛出 `CapabilityNotSupportedError`，需要时用 `client.api.raw()` 走内部接口。
- `bot.version()`：协议没有版本 API，未注册该能力。
- `message.create` 返回消息数组，`SendResult.message_id` 取第一条。

## 常见问题

### 连接被拒绝

先确认协议端已经在监听配置里的地址，再启动机器人。连接失败时框架会按 `runtime.reconnect_max_attempts` 重试，日志形如：

```text
Warning  adapter connection failed: Satori websocket connection to ws://127.0.0.1:5140/v1/events failed: connection refused (check that the Satori end is running and listening on 127.0.0.1:5140); retrying in 1.0s (attempt 1/5)
```

### WebHook 端口启动失败

启动前框架会先确认地址可以监听，端口被占用时日志会直接指出地址：

```text
Error  Satori listener on 127.0.0.1:5141 failed: address already in use (another process is already listening on 127.0.0.1:5141)
```

### API 返回 401

`access_token` 不一致。WebSocket 方式确认协议端的 token；WebHook 方式还要确认推送请求带上了 `token`。

### API 报「unsupported capability」

两种可能：协议端返回 404（该平台没有这个 API），或者适配器没有注册这个能力。前者可以换平台或走 `client.api.raw()`，后者说明协议没有标准化该功能。

### 撤回消息失败

确认消息 ID 来自本框架的事件或发送结果。适配器把频道 ID 编进了消息 ID，外面拿到的裸 ID 用不了。
