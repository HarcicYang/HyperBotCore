# 消息与消息段

## Message

`Message` 是消息段的容器，支持迭代、索引、拼接和序列化。

```python
from hyperot.segments import Text, At, Image, Reply
from hyperot.common import Message

# 构造器
msg = Message(
    Reply(str(message_id)),
    At(qq=str(user_id)),
    Text(" 你好！")
)

# 操作
msg.add(Text("追加"))
str(msg)              # 人类可读的字符串表示
await msg.get()       # 序列化为 OneBot JSON 数组（异步）
msg.get_sync()        # 同步版本
msg + other_msg       # 拼接两个消息

# 索引与迭代
msg[0]                # 第一个消息段
len(msg)              # 消息段数量
for seg in msg: ...   # 迭代消息段
```

## MessageBuilder（链式构建）

```python
msg = Message.builder \
    .text("Hello") \
    .at("123456") \
    .image(file="file:///path/to/image.png") \
    .build()
```

## 消息段类型

### 基础消息段

| 段类型 | OneBot type | 构造 |
|---------|-------------|------|
| `Text` | `text` | `Text(text: str)` |
| `At` | `at` | `At(qq: str)` |
| `Faces` | `face` | `Faces(id: str)` |
| `Dice` | `dice` | `Dice()` |
| `Rps` | `rps` | `Rps()` |

### 媒体消息段

媒体段继承自 `MediaSeg`，提供 `build(file)` 类方法自动将相对路径转为 `file://` 绝对路径。

| 段类型 | OneBot type | 构造 |
|---------|-------------|------|
| `Image` | `image` | `Image(file: str, summary="[Image]", url=None)` |
| `Record` | `record` | `Record(file: str, url=None)` |
| `Video` | `video` | `Video(file: str, url=None)` |

`file` 参数支持 `file://`、`http://`/`https://`、`base64://` 前缀。

```python
Image(file="file:///absolute/path/to/image.png")
Image(file="https://example.com/image.png")
Image(file="base64://iVBORw0KGgo...")
Image.build("./relative/path.png")  # 自动转为 file:// 绝对路径
```

### 交互消息段

| 段类型 | OneBot type | 构造 |
|---------|-------------|------|
| `Reply` | `reply` | `Reply(id: str)` — 通过消息 ID 回复 |
| `Poke` | `poke` | `Poke(type: str, id: str)` |
| `Contact` | `contact` | `Contact(type: str, id: str)` — 推荐用户或群 |

### 富媒体消息段

| 段类型 | OneBot type | 构造 |
|---------|-------------|------|
| `Forward` | `forward` | `Forward(id: str)` — 引用转发消息 |
| `Node` | `node` | `Node(user_id, nickname, content)` — 转发节点 |
| `Json` | `json` | `Json(data: dict | list | str)` — JSON 卡片 |
| `Music` | `music` | `Music(type, url=None, id=None, audio=None, title=None)` |
| `LongMessage` | `longmsg` | `LongMessage(id: str)` — 长消息引用 |
| `MarketFace` | `mface` | `MarketFace(face_id, tab_id, key)` — 商城表情 |

## 自定义消息段

### CustomNode

构建合并转发节点：

```python
from hyperot.segments import CustomNode

node = CustomNode(
    user_id="123456",
    nick_name="用户名",
    content=Message(Text("转发内容"))
)
```

### KeyBoard

构建交互式按钮键盘：

```python
from hyperot.segments import KeyBoard, KeyBoardRow, KeyBoardButton

btn = KeyBoardButton(
    text="确认",
    style=1,         # 0=灰色, 1=蓝色
    button_type=2,   # 2=回调
    data="confirm",
    enter=False,
    permission=2     # 0=所有人, 1=管理员, 2=指定用户
)
row = KeyBoardRow([btn])
kb = KeyBoard([row])
```

### MarkDown

发送 Markdown 格式消息：

```python
from hyperot.segments import MarkDown, MarkdownContent

content = MarkdownContent("# 标题\n这是 **加粗文本**")
md = MarkDown(content)
```
