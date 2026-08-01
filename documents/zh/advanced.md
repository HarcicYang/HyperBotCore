# 高级用法

## 日志系统

```python
from hyperot.hyperogger import Logger

logger = Logger()
logger.set_level("DEBUG")
logger.info("信息")
logger.warning("警告")
logger.error("错误")
logger.exception("异常")  # 在 except 块中调用，附带 traceback
logger.debug("调试")
logger.trace("追踪")
logger.critical("严重")

# 命名日志实例（create 后可用 fetch 获取）
Logger.create("my_module", "DEBUG")
logger2 = Logger.fetch("my_module")
```

框架内部模块（如 `hyperot.protocol.listener`、`hyperot.adapter.onebot.actions`）也会以对应 key 注册命名日志实例，可用 `Logger.fetch("hyperot.protocol.listener")` 获取。

## 异常类型

`hyperot.utils.errors` 提供框架自定义异常：

| 异常 | 说明 |
|------|------|
| `ArgsInvalidError` | API 参数无效（如 `send_msg` 未指定群/私聊目标） |
| `ListenerNotRegisteredError` | 监听器未注册 handler |
| `ButtonRowFulledError` | 键盘按钮行已满（超过 5 个） |
| `ConfigError` | 配置错误 |
| `BotOfflineError` | 机器人离线 |
| `ApiError` | 协议端 API 响应异常（非 JSON 响应，如协议端 500） |

## 合并转发 CustomNode

```python
from hyperot.segments import CustomNode
from hyperot.common import Message
from hyperot.segments import Text

node = CustomNode(
    user_id="123456",
    nick_name="用户名",
    content=Message(Text("转发内容"))
)
```

## 进程重启

```python
await cli.restart()  # 停止监听器并用 os.execv 重启进程
```

适用于热重载场景。注意：`os.execv` 会完全替换当前进程。

## 自定义协议适配器

框架通过 `hyperot.adapters.registry`（适配器注册表）动态加载协议。内置协议（`OneBot` / `Milky`）以 loader 函数表形式注册，未知协议名抛出 `NotImplementedError`。接入新协议有三种方式：

### 1. 运行时注册（推荐）

实现 `ActionsBase`（全部 API）与 `BaseListener`（hooks）后注册：

```python
from hyperot.adapters import Adapter, registry
from hyperot.utils import KeyQueue

def build_my_adapter() -> Adapter:
    return Adapter(
        name="MyProto",
        actions_cls=MyActions,     # 继承 hyperot.protocol.ActionsBase
        listener=MyListener(),     # 继承 hyperot.protocol.BaseListener
        reports=KeyQueue(),        # echo 响应队列（无需 echo 机制可传空实例）
    )

registry.register_loader("MyProto", build_my_adapter)
```

之后在 `config.json` 中设置 `"protocol": "MyProto"` 并正常调用 `hyperot.init()` 即可。

### 2. entry points 自动发现

第三方协议包在 `pyproject.toml` 声明后，pip 安装即自动可见，无需注册：

```toml
[project.entry-points."hyperot.adapters"]
MyProto = "my_protocol_pkg:build_my_adapter"
```

`build_my_adapter` 需为返回 `Adapter` 的可调用对象（loader 函数）。entry points 仅在配置的协议未命中已注册 loader 时扫描，不影响启动性能。

### 3. 内置表

框架内置适配器同样走 loader 表（`hyperot/adapters/__init__.py`），新增内置协议只需添加一个 loader 函数与一行注册。
