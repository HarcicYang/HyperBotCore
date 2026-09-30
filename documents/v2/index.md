# HyperBotCore V2

V2 lives under `hyperot.v2`. V1 remains available under the original `hyperot.*` modules.

- [快速开始](getting-started.md)
- [配置](configuration.md)
- [OneBot 适配器](onebot.md)

## 设计边界

- 一个 Client 管理一个账号和一个适配器。
- 公共事件和消息段不包含 OneBot 协议字段。
- 事件总线只接受已经构造完成的 Pydantic `Event`。
- 用户 API 通过 `client.api` 调用。
- 适配器负责协议、平台、Echo、消息段和异常转换。
- 日志视觉格式保留 EulerOneBot 配色，实际输出交给标准库 `logging`。
