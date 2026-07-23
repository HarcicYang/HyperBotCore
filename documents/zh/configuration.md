# 配置文件

在项目根目录创建 `config.json`：

```json
{
  "protocol": "OneBot",
  "owner": [],
  "black_list": [],
  "silents": [],
  "connection": {
    "mode": "FWS",
    "host": "127.0.0.1",
    "port": 5004
  },
  "log_level": "INFO",
  "log_use_nf": true,
  "uin": 0,
  "max_workers": 25,
  "others": {}
}
```

## 字段说明

| 字段                | 类型                  | 说明                                                                 |
|-------------------|---------------------|--------------------------------------------------------------------|
| `protocol`        | `str`               | 协议类型，目前仅支持 `"OneBot"`                                              |
| `owner`           | `list[int]`         | 主人 QQ 号列表，消息 `is_owner = True`                                     |
| `black_list`      | `list[int]`         | 黑名单 QQ 号列表，消息 `blocked = True`                                     |
| `silents`         | `list[int]`         | 静默列表，消息 `is_silent = True`                                         |
| `connection.mode` | `"FWS"` / `"HTTPC"` | 连接模式                                                               |
| `connection.host` | `str`               | OneBot 实现地址                                                        |
| `connection.port` | `int`               | OneBot 实现端口                                                        |
| `log_level`       | `str`               | 日志等级：`DEBUG` / `TRACE` / `INFO` / `WARNING` / `ERROR` / `CRITICAL` |
| `log_use_nf`      | `bool`              | 是否启用 NerdFont 图标                                                   |
| `max_workers`     | `int`               | 最大并发任务数                                                            |
| `others`          | `dict`              | 自定义扩展配置                                                            |

## WebSocket 模式 (FWS)

| 字段                   | 类型    | 默认值  | 说明       |
|----------------------|-------|------|----------|
| `connection.retries` | `int` | `5`  | 连接失败重试次数 |
| `connection.auth`    | `str` | `""` | 鉴权 Token |

## HTTP 回调模式 (HTTPC)

| 字段                         | 类型    | 说明       |
|----------------------------|-------|----------|
| `connection.listener_host` | `str` | 回调监听地址   |
| `connection.listener_port` | `int` | 回调监听端口   |
| `connection.auth`          | `str` | 鉴权 Token |

`hyperot.init()` 会自动加载配置。如果文件不存在，会自动创建模板后退出。
