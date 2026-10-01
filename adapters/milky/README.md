# Hyperot Milky Adapter

Milky protocol adapter for `hyperot.v2`, implementing Milky 1.3.

Install the adapter from PyPI:

```shell
pip install hyperot-adapter-milky
```

The package registers the `milky` adapter through the `hyperot.adapters` entry-point group.

Supported connection types:

- `WebSocket` -- the framework opens a WebSocket to the `/event` endpoint and calls APIs over HTTP.
- `SSE` -- the framework subscribes to the `/event` endpoint with Server-Sent Events.
- `WebHook` -- the framework serves an HTTP endpoint the protocol end posts events to.

The package contains `manifest.json`, which is loaded by `hyperot.v2.Client.from_appconfig()`.
