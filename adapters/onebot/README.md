# Hyperot OneBot Adapter

OneBot v11 adapter for `hyperot.v2`.

Install the adapter from PyPI:

```shell
pip install hyperot-adapter-onebot
```

The package registers the `onebot` adapter through the `hyperot.adapters` entry-point group.

Supported connection types:

- `ForwardWebSocket`
- `ReverseWebSocket`
- `HTTP`
- `HTTPPost`

The package contains `manifest.json`, which is loaded by `hyperot.v2.Client.from_appconfig()`.
