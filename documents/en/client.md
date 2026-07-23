# Client & Lifecycle

The `Client` class manages event subscriptions and the bot lifecycle.

## Basic Usage

```python
from hyperot import Client
from hyperot.events import GroupMessageEvent, PrivateMessageEvent

cli = Client()
cli.subscribe(handler, GroupMessageEvent)  # Single event type
cli.subscribe(handler, [GroupMessageEvent, PrivateMessageEvent])  # Multiple
asyncio.get_event_loop().run_until_complete(cli.run())  # Start (blocking)
cli.restart()  # Restart process
```

## Context Manager

`Client` supports both sync and async context managers:

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

- `func` — an `async` function receiving `(event, actions)`
- `event` — a single event class or a list of event classes

Multiple handlers can be subscribed to the same event type; they run concurrently.

## run()

Starts the listener and blocks until interrupted (SIGINT/SIGTERM on Linux, SIGINT/SIGBREAK on Windows). This is an async method — it must be run within an event loop.

## restart()

Stops the listener, then re-executes the current process via `os.execv`.
