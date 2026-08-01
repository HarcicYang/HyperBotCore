# HypeR Bot 文档

HypeR Core 是一个基于 asyncio 的 QQ 机器人框架，同时适配 OneBot v11 与 Milky 协议。

## 目录

- [快速开始](zh/getting-started.md) —— 安装、协议端部署、快速开始
- [配置文件](zh/configuration.md) —— `config.json` 参考（FWS、HTTPC 与 Milky 模式）
- [Client 与生命周期](zh/client.md) —— `Client` 类、`subscribe()`、`run()`、`restart()`
- [事件系统](zh/events.md) —— 全部事件类型及其属性
- [消息与消息段](zh/messages.md) —— `Message`、消息段类型、构建器、KeyBoard、MarkDown
- [Actions API](zh/actions.md) —— 全部 OneBot API 方法及 `Ret<T>` 响应
- [高级用法](zh/advanced.md) —— 日志、键盘、Markdown、CustomNode、重启、自定义协议适配器

## 许可

GPL-3.0
