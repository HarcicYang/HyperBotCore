# Configuration

Create `config.json` in your bot project root:

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

## Fields

| Field | Type | Description |
|--------|------|-------------|
| `protocol` | `str` | Protocol type, currently `"OneBot"` |
| `owner` | `list[int]` | Owner QQ IDs, messages get `is_owner = True` |
| `black_list` | `list[int]` | Blacklisted QQ IDs, messages get `blocked = True` |
| `silents` | `list[int]` | Silent list, messages get `is_silent = True` |
| `connection.mode` | `"FWS"` / `"HTTPC"` | Connection mode |
| `connection.host` | `str` | OneBot implementation address |
| `connection.port` | `int` | OneBot implementation port |
| `log_level` | `str` | Log level: `DEBUG` / `TRACE` / `INFO` / `WARNING` / `ERROR` / `CRITICAL` |
| `log_use_nf` | `bool` | Enable NerdFont icons in logs |
| `max_workers` | `int` | Max concurrent tasks |
| `others` | `dict` | Custom extension config |

## WebSocket Mode (FWS)

| Field | Type | Default | Description |
|--------|------|---------|-------------|
| `connection.retries` | `int` | `5` | Retry count on connect failure |
| `connection.auth` | `str` | `""` | Auth token |

## HTTP Callback Mode (HTTPC)

| Field | Type | Description |
|--------|------|-------------|
| `connection.listener_host` | `str` | Callback listen address |
| `connection.listener_port` | `int` | Callback listen port |
| `connection.auth` | `str` | Auth token |

The `hyperot.init()` function loads config automatically. If the file doesn't exist, it creates a template and exits.
