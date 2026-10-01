# 进阶用法

这一页给需要更精细控制生命周期、日志、异常和适配器的项目使用。普通机器人开发可以先跳过。

## 日志

日志由 `logging` 配置控制：

```json
{
  "logging": {
    "level": "INFO",
    "use_nerd_font": false,
    "global_handlers": false,
    "stream": "stdout"
  }
}
```

建议开发时使用 `TRACE` `DEBUG`，生产环境使用 `INFO` 或 `WARNING`。

> [!NOTE]
> 在本项目的日志系统中，`TRACE` 是等价的 `DEBUG` 实现，而 `DEBUG` 层级是非常高的，他会永远显示。

```python
from hyperot.v2.hyperogger import Logger

logger = Logger.fetch("my_bot")
logger.info("机器人已启动")
logger.warning("配置里没有管理员")
```

## 异常处理

常见异常：

| 异常 | 说明 |
| --- | --- |
| `ConfigurationError` | 配置错误，例如适配器未安装或字段不合法。 |
| `AdapterConnectionError` | 适配器连接失败。 |
| `AdapterDisconnectedError` | 适配器连接已断开。 |
| `ActionTimeoutError` | API 调用超时。 |
| `ActionRejectedError` | 协议端拒绝了操作。 |
| `CapabilityNotSupportedError` | 当前适配器不支持这个操作。 |
| `ClientNotRunningError` | 客户端未启动时调用了 API。 |

API 失败示例：

```python
from hyperot.v2.common import ActionRejectedError, ActionTimeoutError

try:
    await client.api.group(group_id).send("hello")
except ActionTimeoutError:
    ...
except ActionRejectedError:
    ...
```

事件处理器里没有捕获的异常不会让整个机器人退出，但会记录错误日志。建议在关键业务里自行捕获并处理。

## 重连

连接断开后，框架会按 `runtime` 配置重试：

```json
{
  "runtime": {
    "reconnect_initial_delay": 1.0,
    "reconnect_max_delay": 30.0,
    "reconnect_max_attempts": 5
  }
}
```

如果希望一直重连：

```json
{
  "runtime": {
    "reconnect_max_attempts": null
  }
}
```

达到重试上限后，`run()` 会退出并抛出最后一次错误。

## 并发处理

同一个事件可以订阅多个处理器，它们会并发执行：

```python
client.subscribe(MessageReceivedEvent, log_message)
client.subscribe(MessageReceivedEvent, handle_command)
```

某个处理器变慢不会阻塞其他处理器。需要串行处理时，请在自己的业务代码里加锁或队列。

## 手动发送事件

外部系统可以通过 `client.emit()` 把事件送进框架：

```python
await client.emit(custom_event)
```

事件必须已经是 V2 的事件对象，不能直接传字典。

## 扩展接口

某些适配器会提供公共 API 之外的扩展能力：

```python
extension = client.extension(MyAdapterInterface)
```

没有对应扩展时会抛出异常。扩展接口通常用于访问协议端特有能力，不建议普通业务依赖。

## 自定义适配器

适配器是独立安装的包，通过入口点自动发现。一个适配器通常需要提供：

- 适配器 ID。
- 配置模型。
- 连接和事件转换。
- 用户可调用的 API。

第三方适配器安装后，只要在 `appconfig.json` 中设置 `active_adapter` 即可使用。

```json
{
  "active_adapter": "my-adapter"
}
```
