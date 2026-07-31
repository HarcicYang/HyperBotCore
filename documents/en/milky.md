# Milky Protocol

[Milky](https://milky.ntqqrev.org/) is a next-generation QQ bot interface standard built on HTTP / WebSocket. HypeR Core acts as the application side: it receives event pushes over WebSocket (`/event`) and calls the protocol implementation's API over HTTP (`/api/:api`).

## Protocol Implementations

You need a Milky-compatible implementation, for example:

- [Lagrange.Milky](https://github.com/LagrangeDev/Lagrange.Core) (the `Lagrange.Milky` project in the Lagrange.Core repository)
- [Yogurt](https://acidify.ntqqrev.org/yogurt/start)
- [LuckyLilliaBot](https://github.com/LLOneBot/LLOneBot)

The protocol implementation is ready when `POST /api/get_impl_info` returns `{"status": "ok", ...}`.

## Configuration

Create `milky_config.json` (like `config.json`, it is gitignored):

```json
{
  "protocol": "Milky",
  "owner": [],
  "black_list": [],
  "silents": [],
  "connection": {
    "mode": "Milky",
    "host": "127.0.0.1",
    "port": 5005,
    "auth": ""
  },
  "log_level": "INFO",
  "log_use_nf": false,
  "uin": 0,
  "max_workers": 1,
  "others": {}
}
```

`host` / `port` point to the protocol implementation's HTTP service, `auth` is the `access_token` (empty if not set). See [configuration](configuration.md) for field details.

## Quick Start

```python
import asyncio
import hyperot

logger = hyperot.init("milky_config.json")

from hyperot import Client
from hyperot.events import GroupMessageEvent, PrivateMessageEvent

async def handler(event, actions):
    if str(event.message) == ".ping":
        await actions.send_msg("pong", group_id=event.group_id, user_id=event.user_id)

with Client() as cli:
    cli.subscribe(handler, [GroupMessageEvent, PrivateMessageEvent])
    asyncio.get_event_loop().run_until_complete(cli.run())
```

The repository also ships `test_milky.py`, a live integration script (`uv run python test_milky.py`) covering event receiving, read-only APIs, sending and recalling messages (send `.e2e` to the bot in QQ to trigger it).

## Event Mapping

Milky events are mapped onto the framework's [event model](events.md):

| Milky event | Framework event |
|-------------|-----------------|
| `message_receive` (`friend` / `group` / `temp`) | `PrivateMessageEvent` / `GroupMessageEvent` (temp sessions are treated as private) |
| `bot_offline` | `BotOnLineEvent` |
| `message_recall` | `FriendRecallEvent` / `GroupRecallEvent` |
| `group_admin_change` | `GroupAdminEvent` |
| `group_essence_message_change` | `GroupEssenceEvent` |
| `group_member_increase` / `group_member_decrease` | `GroupMemberIncreaseEvent` / `GroupMemberDecreaseEvent` |
| `group_mute` | `GroupMuteEvent` |
| `group_whole_mute` | `GroupWholeMuteEvent` |
| `group_name_change` | `GroupNameChangeEvent` |
| `group_invitation` | `GroupInvitationEvent` |
| `group_file_upload` / `friend_file_upload` | `GroupFileUploadEvent` / `FriendFileUploadEvent` |
| `group_message_reaction` | `MessageReactionEvent` |
| `group_nudge` / `friend_nudge` | `NotifyEvent` (`sub_type = "poke"`) |
| `friend_request` | `FriendAddRequestEvent` (`flag` is `initiator_uid`) |
| `group_join_request` / `group_invited_join_request` | `GroupAddInviteEvent` (`flag` encoded as `"{group_id}:{notification_seq}"`) |

Other event types (e.g. `peer_pin_change`) have no corresponding event class yet; they are logged and skipped without breaking the connection.

## Message Segments

- **Incoming**: `text`, `mention`, `mention_all`, `face`, `reply`, `image`, `record`, `video`, `forward`, `market_face`, `light_app`, `xml` (`file` and unknown types are skipped)
- **Outgoing**: `Text`, `At` (`qq="all"` becomes `mention_all`), `Reply`, `Faces`, `Image`, `Record`, `Video`, `Forward` (node lists become `outgoing_forward`)

## Actions

All [standard Actions methods](actions.md) are available under Milky:

- `send_msg` / `del_msg`: `message_id` encodes `scene + seq + peer`; `del_msg` decodes it automatically and calls the matching recall API
- Queries work: `get_login_info`, `get_version_info` (maps to `get_impl_info`), `get_group_info`, `get_group_member_info`, `get_stranger_info` (maps to `get_user_profile`), etc.
- Group management works: `set_group_kick`, `set_group_ban`, `set_group_special_title`, `set_group_add_request`, `set_essence_msg`, etc.
- `actions.custom` can call Milky-specific APIs (e.g. `set_group_whole_mute`, `set_group_member_card`, `send_group_nudge`) and **returns the response `data` dict** (unlike OneBot, which returns an echo)

## Known Limitations

- `send_forward_msg` (no target scene) and `send_callback` are not supported yet and raise `NotImplementedError`; use `send_group_forward_msg` for forwarded messages
- Some protocol implementations (e.g. certain Lagrange.Milky builds) have a protocol-side bug in `recall_private_message` (`GetC2CMessage` fails); private recall may fail, group recall is unaffected
