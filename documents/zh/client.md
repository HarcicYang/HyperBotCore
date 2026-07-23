# Client 与生命周期

`Client` 类管理事件订阅和机器人生命周期。

## 基本用法

```python
from hyperot import Client
from hyperot.events import GroupMessageEvent, PrivateMessageEvent

cli = Client()
cli.subscribe(handler, GroupMessageEvent)  # 订阅单个事件类型
cli.subscribe(handler, [GroupMessageEvent, PrivateMessageEvent])  # 订阅多个
asyncio.get_event_loop().run_until_complete(cli.run())  # 启动（阻塞）
cli.restart()  # 重启进程
```

## 上下文管理器

支持同步和异步上下文管理器：

```python
with Client() as cli:
    cli.subscribe(handler, GroupMessageEvent)
    asyncio.get_event_loop().run_until_complete(cli.run())
```

```python
async with Client() as cli:
    cli.subscribe(handler, GroupMessageEvent)
    await cli.run()
```

## subscribe()

```python
def subscribe(func: Callable, event: type | list[type]) -> None
```

- `func` — 异步函数，参数为 `(event, actions)`
- `event` — 单个事件类，或事件类列表

同个事件类型可注册多个 handler，它们会并发执行。

## run()

启动监听器并阻塞直到被中断（Linux 下 SIGINT/SIGTERM，Windows 下 SIGINT/SIGBREAK）。这是异步方法，必须在事件循环中运行。

## restart()

停止监听器，然后通过 `os.execv` 重启当前进程。
