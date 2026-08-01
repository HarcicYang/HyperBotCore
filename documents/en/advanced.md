# Advanced

## Logging

```python
from hyperot.hyperogger import Logger

logger = Logger()
logger.set_level("DEBUG")
logger.info("Info message")
logger.warning("Warning")
logger.error("Error")
logger.exception("Exception")  # Call inside an except block; appends the traceback
logger.debug("Debug")
logger.trace("Trace")
logger.critical("Critical")

# Named loggers
logger2 = Logger.fetch("my_module")

```

## Exceptions

`hyperot.utils.errors` provides framework exceptions:

| Exception | Description |
|-----------|-------------|
| `ArgsInvalidError` | Invalid API arguments (e.g. `send_msg` without a group/private target) |
| `ListenerNotRegisteredError` | Listener has no registered handler |
| `ButtonRowFulledError` | Keyboard button row is full (more than 5) |
| `ConfigError` | Configuration error |
| `BotOfflineError` | Bot offline |
| `ApiError` | Abnormal protocol implementation API response (non-JSON, e.g. HTTP 500) |

## Forward Messages with CustomNode

```python
from hyperot.segments import CustomNode
from hyperot.common import Message
from hyperot.segments import Text

node = CustomNode(
    user_id="123456",
    nick_name="Username",
    content=Message(Text("Forwarded content"))
)
```

## Process Restart

```python
await cli.restart()  # Stops the listener and re-execs the process
```

Handy for hot-reload scenarios. Note: `os.execv` replaces the current process entirely.
