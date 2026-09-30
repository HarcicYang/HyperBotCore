# OneBot 适配器

OneBot 适配器实现位于 `adapters/onebot`，发布包名为 `hyperot-adapter-onebot`。

```shell
pip install hyperot-adapter-onebot
```

安装后通过 `hyperot.adapters` entry-point 组自动发现，无需额外注册。

支持四种连接类型：

- `ForwardWebSocket`：框架连接 OneBot 端 WebSocket。
- `ReverseWebSocket`：框架监听 API 与事件 WebSocket。
- `HTTP`：框架通过 HTTP 调用 OneBot Action。
- `HTTPPost`：OneBot 端向框架推送事件。

## 本地 EulerOneBot 测试

live 测试默认关闭。启用后，测试会从 `lagrange-python` 读取 UIN、`device.json` 和 `sig.bin`，并在临时目录启动本地 EulerOneBot：

```shell
HYPEROT_EULER_LIVE=1 \
HYPEROT_EULER_ROOT=/path/to/EulerOneBot \
HYPEROT_LAGRANGE_PYTHON_ROOT=/path/to/lagrange-python \
.venv/bin/python -m pytest -q -m euler_live tests/v2/euler_live
```

默认安全测试目标：

- 群：`623371208`
- 用户：`2488529467`

可通过 `HYPEROT_TEST_GROUP_ID` 和 `HYPEROT_TEST_USER_ID` 覆盖。群踢人、禁言、修改群名、退出群等破坏性测试需要显式设置 `HYPEROT_ALLOW_DESTRUCTIVE_E2E=1`。
