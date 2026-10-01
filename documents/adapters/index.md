# 适配器文档

V2 本体不绑定具体协议。每个适配器都有自己的安装方式、连接配置、事件映射和扩展 API，因此单独维护文档。

## 已提供文档

- [OneBot v11](onebot.md)

## 适配器负责什么

适配器是框架和具体协议之间的桥梁。它负责：

- 连接协议端。
- 把协议事件转换成 V2 公共事件。
- 把 `client.api` 调用转换成协议 API。
- 处理协议特有的连接方式、鉴权、消息段和扩展能力。

业务代码通常只需要使用 [V2 API](../v2/api.md) 和 [V2 事件](../v2/events.md)。只有需要协议特有功能时，才需要阅读对应适配器文档。

## 安装与选择

先安装框架本体：

```shell
pip install hyper-bot
```

再安装一个适配器包，例如：

```shell
pip install hyperot-adapter-onebot
```

然后在 `appconfig.json` 中设置：

```json
{
  "active_adapter": "onebot"
}
```

`adapter_config` 的内容由对应适配器决定。具体字段请查看该适配器的文档。

## 新增适配器

第三方适配器安装后，只要注册了对应 ID，就可以通过 `active_adapter` 使用。每新增一个适配器，应在本目录增加单独的文档页，避免把协议细节混进 V2 公共文档。
