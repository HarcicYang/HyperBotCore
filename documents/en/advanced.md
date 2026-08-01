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

## Custom Protocol Adapters

Adapters are loaded dynamically through `hyperot.adapters.registry`. Built-in protocols (`OneBot` / `Milky`) are registered as a loader table; unknown protocol names raise `NotImplementedError`. Three ways to plug in a new protocol:

### 1. Runtime registration (recommended)

Implement `ActionsBase` (all APIs) and `BaseListener` (hooks), then register:

```python
from hyperot.adapters import Adapter, registry
from hyperot.utils import KeyQueue

def build_my_adapter() -> Adapter:
    return Adapter(
        name="MyProto",
        actions_cls=MyActions,     # subclass hyperot.protocol.ActionsBase
        listener=MyListener(),     # subclass hyperot.protocol.BaseListener
        reports=KeyQueue(),        # echo response queue (pass an empty one if not needed)
    )

registry.register_loader("MyProto", build_my_adapter)
```

Then set `"protocol": "MyProto"` in `config.json` and call `hyperot.init()` as usual.

### 2. Entry points auto-discovery

A third-party protocol package can declare itself in `pyproject.toml`; it becomes visible after `pip install`, no registration needed:

```toml
[project.entry-points."hyperot.adapters"]
MyProto = "my_protocol_pkg:build_my_adapter"
```

`build_my_adapter` must be a callable returning an `Adapter` (loader function). Entry points are only scanned when the configured protocol is not found among registered loaders, so startup performance is unaffected.

### 3. Built-in table

Built-in adapters use the same loader table (`hyperot/adapters/__init__.py`); adding one requires only a loader function plus one registration line.
