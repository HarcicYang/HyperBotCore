# Messages & Segments

## Message

`Message` is a container of message segments. It supports iteration, indexing, concatenation, and serialization.

```python
from hyperot.segments import Text, At, Image, Reply
from hyperot.common import Message

# Constructor
msg = Message(
    Reply(str(message_id)),
    At(qq=str(user_id)),
    Text(" Hello!")
)

# Operations
msg.add(Text("more"))
str(msg)              # Human-readable string representation
await msg.get()       # Serialize to OneBot JSON array (async)
msg.get_sync()        # Synchronous version
msg + other_msg       # Concatenate two messages

# Indexing & iteration
msg[0]                # First segment
len(msg)              # Number of segments
for seg in msg: ...   # Iterate segments
```

## MessageBuilder (Fluent API)

```python
msg = Message.builder \
    .text("Hello") \
    .at("123456") \
    .image(file="file:///path/to/image.png") \
    .build()
```

## Segment Types

### Basic Segments

| Segment | Type | Constructor |
|---------|------|-------------|
| `Text` | `text` | `Text(text: str)` |
| `At` | `at` | `At(qq: str)` |
| `Faces` | `face` | `Faces(id: str)` |
| `Dice` | `dice` | `Dice()` |
| `Rps` | `rps` | `Rps()` |

### Media Segments

Media segments inherit from `MediaSeg` and provide a `build(file)` class method that auto-converts relative paths to `file://` absolute paths.

| Segment | Type | Constructor |
|---------|------|-------------|
| `Image` | `image` | `Image(file: str, summary="[Image]", url=None)` |
| `Record` | `record` | `Record(file: str, url=None)` |
| `Video` | `video` | `Video(file: str, url=None)` |

The `file` parameter supports `file://`, `http://`/`https://`, and `base64://` prefixes.

```python
Image(file="file:///absolute/path/to/image.png")
Image(file="https://example.com/image.png")
Image(file="base64://iVBORw0KGgo...")
Image.build("./relative/path.png")  # Auto-converts to file:// absolute
```

### Interaction Segments

| Segment | Type | Constructor |
|---------|------|-------------|
| `Reply` | `reply` | `Reply(id: str)` — reply to a message by ID |
| `Poke` | `poke` | `Poke(type: str, id: str)` |
| `Contact` | `contact` | `Contact(type: str, id: str)` — recommend user or group |

### Rich Content Segments

| Segment | Type | Constructor |
|---------|------|-------------|
| `Forward` | `forward` | `Forward(id: str)` — reference a forward message |
| `Node` | `node` | `Node(user_id, nickname, content)` — forward message node |
| `Json` | `json` | `Json(data: dict | list | str)` — JSON card |
| `Music` | `music` | `Music(type, url=None, id=None, audio=None, title=None)` |
| `LongMessage` | `longmsg` | `LongMessage(id: str)` — long message reference |
| `MarketFace` | `mface` | `MarketFace(face_id, tab_id, key)` — marketplace emoji |

## Custom Segments

### CustomNode

Used to build nodes for forwarding messages:

```python
from hyperot.segments import CustomNode

node = CustomNode(
    user_id="123456",
    nick_name="Username",
    content=Message(Text("Forwarded content"))
)
```

### KeyBoard

Build interactive button keyboards:

```python
from hyperot.segments import KeyBoard, KeyBoardRow, KeyBoardButton

btn = KeyBoardButton(
    text="Confirm",
    style=1,         # 0=grey, 1=blue
    button_type=2,   # 2=callback
    data="confirm",
    enter=False,
    permission=2     # 0=all, 1=admin, 2=specified
)
row = KeyBoardRow([btn])
kb = KeyBoard([row])
```

### MarkDown

Send Markdown-formatted messages:

```python
from hyperot.segments import MarkDown, MarkdownContent

content = MarkdownContent("# Title\nThis is **bold text**")
md = MarkDown(content)
```
