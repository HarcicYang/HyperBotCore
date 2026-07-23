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

# 注册全局未处理异常钩子
logger.register_hook()
```

## 按钮键盘

```python
from hyperot.segments import KeyBoard, KeyBoardRow, KeyBoardButton

btn = KeyBoardButton(
    text="确认",
    style=1,         # 0=灰色, 1=蓝色
    button_type=2,   # 2=回调（默认）
    data="confirm",
    enter=False,
    permission=2,    # 0=所有人, 1=管理员, 2=指定用户
    specify_user_ids=None
)
row = KeyBoardRow([btn])
kb = KeyBoard([row])

# 通过自定义 API 发送
await actions.custom.send_group_bot_callback(
    group_id=123456,
    bot_id=bot_qq,
    **kb.to_json()
)
```

## Markdown 消息

```python
from hyperot.segments import MarkDown, MarkdownContent

content = MarkdownContent("# 标题\n这是 **加粗** 文本")
md = MarkDown(content)
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
