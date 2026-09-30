# V2 配置

V2 使用单个 `appconfig.json`。

```json
{
  "schema_version": 1,
  "active_adapter": "onebot",
  "adapter_config": {
    "connections": [
      {
        "type": "ForwardWebSocket",
        "url": "ws://127.0.0.1:5004"
      }
    ]
  },
  "runtime": {
    "reconnect_initial_delay": 1.0,
    "reconnect_max_delay": 30.0,
    "reconnect_max_attempts": 5,
    "shutdown_timeout": 10.0,
    "action_timeout": 30.0
  },
  "logging": {
    "level": "INFO",
    "use_nerd_font": false,
    "global_handlers": false,
    "stream": "stdout"
  }
}
```

`active_adapter` 指向已安装适配器注册的 entry-point 名称。适配器通过 PyPI 安装，例如
`pip install hyperot-adapter-onebot`。`adapter_config` 由当前适配器的 Pydantic 配置模型解析。
