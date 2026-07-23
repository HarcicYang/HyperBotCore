# Advanced

## Logging

```python
from hyperot.hyperogger import Logger

logger = Logger()
logger.set_level("DEBUG")
logger.info("Info message")
logger.warning("Warning")
logger.error("Error")
logger.debug("Debug")
logger.trace("Trace")
logger.critical("Critical")

# Named loggers
logger2 = Logger.fetch("my_module")

```

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
cli.restart()  # Stops the listener and re-execs the process
```

Handy for hot-reload scenarios. Note: `os.execv` replaces the current process entirely.
