# 消息与消息段

`Message` 是一条消息的容器。它由多个“消息段”组成，例如文本、@、图片、引用和转发节点。

## 构造消息

```python
from hyperot.v2 import Message, Text

message = Message(Text(text="你好"))
```

多个消息段按顺序放入：

```python
from hyperot.v2 import Message, Mention, Text

message = Message(
    Text(text="你好 "),
    Mention(user_id="123456"),
    Text(text="，欢迎回来。"),
)
```

也接受段列表或元组，几种写法等价：

```python
segments = [Text(text="你好"), Image(source="https://example.com/a.png")]

message = Message(segments)
message = Message(*segments)
message = Message(tuple(segments))
message = Message(segments=segments)
```

也可以直接构造纯文本：

```python
message = Message.text("你好")
```

## 发送消息

发送字符串时，框架会自动包装成文本消息：

```python
await client.api.group(group_id).send("你好")
```

发送完整消息：

```python
await client.api.group(group_id).send(
    Message(Text(text="图片："), Image(source="https://example.com/a.png"))
)
```

最通用的发送方式是使用当前事件所在的场景：

```python
await client.api.scene(event.scene_type, event.scene_id).send("回复")
```

## Message 常用操作

| 操作 | 说明 |
| --- | --- |
| `Message(Text(...), Image(...))` | 构造一条消息。 |
| `Message.text("你好")` | 构造纯文本消息。 |
| `message.add(segment)` | 追加一个消息段，返回新消息。 |
| `message + other` | 拼接两条消息。 |
| `str(message)` | 得到适合显示或匹配的文本。 |
| `len(message)` | 消息段数量。 |
| `message[0]` | 取出某个消息段。 |
| `for segment in message` | 遍历所有消息段。 |

`str(message)` 适合做命令匹配，例如：

```python
if str(event.message) == ".ping":
    ...
```

## 消息段

### 文本和提及

```python
from hyperot.v2 import Mention, MentionAll, Message, Text

message = Message(
    Text(text="你好 "),
    Mention(user_id="123456"),
    Text(text="，以及 "),
    MentionAll(),
)
```

| 类型 | 说明 |
| --- | --- |
| `Text` | 纯文本。 |
| `Mention` | @ 某个用户。 |
| `MentionAll` | @ 全体成员。 |

### 媒体

```python
from hyperot.v2 import Audio, File, Image, Message, Video

message = Message(
    Image(source="https://example.com/a.png", alt="项目截图"),
    Audio(source="https://example.com/a.mp3"),
    Video(source="https://example.com/a.mp4"),
    File(source="https://example.com/a.zip", name="a.zip", file_id="f1"),
)
```

| 类型 | 说明 |
| --- | --- |
| `Image` | 图片。`source` 可以是 URL、文件标识或适配器支持的其他来源。 |
| `Audio` | 语音。 |
| `Video` | 视频。 |
| `File` | 文件。 |

`Image.alt` 会用于日志和文本显示。没有设置时显示为 `[图片]`。

### 引用、转发和表情

```python
from hyperot.v2 import Face, Forward, ForwardNode, Message, Quote, Text

quoted = Quote(message_id="123")
forwarded = Forward(forward_id="forward-id")

node = ForwardNode(
    user_id="123456",
    display_name="某人",
    message=Message(Text(text="转发内容")),
)

face = Face(face_id="123")
```

| 类型 | 说明 |
| --- | --- |
| `Quote` | 引用一条消息。 |
| `Forward` | 引用合并转发。 |
| `ForwardNode` | 构造合并转发节点。 |
| `Face` | QQ 表情。 |
| `Markdown` | Markdown 内容。 |

消息段是不可变的 dataclass：字段写注解即可，位置参数按字段顺序传入，和 `Face("123", is_large=True)` 一样混用也没问题。`model_dump()`、`model_validate()` 这类 pydantic 接口不再提供，段之间用 `==` 比较即可。

## 消息来源

不同适配器对媒体来源的支持可能不同。常见来源包括：

- 网络 URL。
- 协议端返回的文件标识。
- 适配器支持的本地路径或 Base64 形式。

发送前最好先确认当前适配器和协议端支持哪种来源。具体支持情况见对应适配器文档。

## 收到未知消息段

如果适配器遇到尚未建模的消息段，会尽量保留原始内容，而不是让整条消息失败。文本显示中会看到类似：

```text
[unknown:some_type]
```

普通业务代码通常不需要处理这种情况。需要协议级扩展时，可以读取消息段本身。

## 注册自定义消息段

消息段是标准库 dataclass，写清字段注解即可，位置参数和关键字参数都能用：

```python
from hyperot.v2 import Segment


class WeatherCard(Segment):
    city: str
    temperature: int

    def display_text(self) -> str:
        return f"[天气: {self.city} {self.temperature}°C]"
```

能不能在协议上收发，取决于当前适配器的段注册表。注册之后，自定义段和内置段一样参与消息往返：

```python
from typing import Any

from hyperot.v2 import Segment

codec = client.adapter.segment_codec


def decode_weather(item: dict[str, Any]) -> Segment:
    data = item["data"]
    return WeatherCard(city=data["city"], temperature=data["temperature"])


def encode_weather(segment: Segment) -> dict[str, Any]:
    return {"type": "weather", "data": {"city": segment.city, "temperature": segment.temperature}}


codec.register_segment(
    WeatherCard,
    wire_type="weather",
    decode=decode_weather,
    encode=encode_weather,
)
```

注册表的约定：

- `decode` 收到协议端的原始段并返回段实例；解析失败会自动降级为 `UnknownSegment`，不会让整条消息失败。
- `encode` 把段变成可以直接发送的字典。
- `wire_type` 是协议里的段类型名，重复占用同一个名字会报错，确认要覆盖时加 `replace=True`。
- 没有注册的子类会沿用最近父类的编码器，所以继承内置段一般不需要再注册一次。
- `codec.supports(SomeSegment)` 可以查询某个段能否被当前适配器发送。
