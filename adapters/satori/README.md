# Hyperot Satori Adapter

Satori protocol adapter for `hyperot.v2`, implementing the Satori protocol as specified by
[satorijs/docs](https://github.com/satorijs/docs).

Install the adapter from PyPI:

```shell
pip install hyper-bot hyperot-adapter-satori
```

The package registers the `satori` adapter through the `hyperot.adapters` entry-point group.

Supported connection types:

- `WebSocket` -- the framework opens the event WebSocket at `/v1/events`, sends `IDENTIFY` and
  keeps the connection alive with `PING`, and calls APIs over HTTP.
- `WebHook` -- the framework serves an HTTP endpoint the SDK posts events to, loads the logins
  from `/v1/meta`, and registers the webhook with `meta/webhook.create`.

Both types call APIs over HTTP with the `Satori-Platform` and `Satori-User-ID` headers the
protocol requires.

The package contains `manifest.json`, which is loaded by `hyperot.v2.Client.from_appconfig()`.

Message content is encoded as Satori message elements instead of a segment array, so
`hyperot_adapter_satori.segments` holds both the element parser and the codec that maps
elements onto V2 segments.
