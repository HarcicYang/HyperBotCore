# 高级用法

## 日志系统

```python
from hyperot.hyperogger import Logger

logger = Logger()
logger.set_level("DEBUG")
logger.info("信息")
logger.warning("警告")
logger.error("错误")
logger.debug("调试")
logger.trace("追踪")
logger.critical("严重")

# 命名日志实例
logger2 = Logger.fetch("my_module")
```

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
cli.restart()  # 停止监听器并用 os.execv 重启进程
```

适用于热重载场景。注意：`os.execv` 会完全替换当前进程。
