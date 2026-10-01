# V2 配置

V2 使用一个 `appconfig.json`。一个配置文件对应一个 `Client`，也就是一个机器人账号和一个适配器。

## 完整结构

```json
{
  "schema_version": 1,
  "active_adapter": "<adapter-id>",
  "adapter_config": {},
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

## 顶层字段

| 字段 | 说明 |
| --- | --- |
| `schema_version` | 配置格式版本，目前使用 `1`。 |
| `active_adapter` | 当前使用的适配器 ID。 |
| `adapter_config` | 交给当前适配器解析的配置。不同适配器的字段不同。 |
| `runtime` | 框架运行行为，例如重连、超时和关闭。 |
| `logging` | 日志输出行为。 |

`active_adapter` 必须是已经安装的适配器。先安装对应适配器包，例如：

```shell
pip install <adapter-package>
```

可用适配器和安装方式见[适配器文档](../adapters/index.md)。

## runtime

| 字段 | 默认值 | 说明 |
| --- | --- | --- |
| `reconnect_initial_delay` | `1.0` | 第一次重连前等待的秒数。 |
| `reconnect_max_delay` | `30.0` | 重连等待时间的上限，单位秒。 |
| `reconnect_max_attempts` | `5` | 最多重试几次。设为 `null` 表示一直重试。 |
| `shutdown_timeout` | `10.0` | 停止时等待事件处理完成的秒数。 |
| `action_timeout` | `30.0` | 调用适配器操作时的默认超时，单位秒。 |

如果机器人需要长期在线，并且希望断线后一直重连，可以这样写：

```json
{
  "runtime": {
    "reconnect_max_attempts": null
  }
}
```

如果不想无限重试，就保留一个正整数。达到上限后，`client.run()` 会退出并抛出最后一次连接错误。

## logging

| 字段 | 默认值 | 说明 |
| --- | --- | --- |
| `level` | `"INFO"` | 日志等级：`TRACE`、`DEBUG`、`INFO`、`WARNING`、`ERROR`、`CRITICAL`。 |
| `use_nerd_font` | `false` | 是否使用 Nerd Font 图标。终端字体不支持时保持关闭。 |
| `global_handlers` | `false` | 是否接管根日志配置。一般保持关闭。 |
| `stream` | `"stdout"` | 输出到 `stdout` 或 `stderr`。 |

## adapter_config

`adapter_config` 的内容完全由当前适配器决定。V2 只负责把这段配置交给对应适配器解析。

```json
{
  "active_adapter": "<adapter-id>",
  "adapter_config": {
    "...": "由适配器文档决定"
  }
}
```

适配器会在 `adapter_config` 中配置连接方式、地址和鉴权等协议相关字段。具体字段请查看对应适配器文档。

## 适配器选择

`active_adapter` 是适配器 ID，不是包名，也不是协议名。安装适配器后，使用它声明的 ID。

当前可用的适配器文档见[适配器文档](../adapters/index.md)。

## 配置检查建议

- 一个 `Client` 只使用一个账号。多账号请启动多个进程或多个 `Client` 实例。
- 使用 `client.run()` 前先确认协议端已经启动。
- `adapter_config` 字段填错时，优先对照对应适配器文档。
- 协议端连接地址、鉴权和事件上报方式都属于适配器配置，不属于 V2 顶层配置。
