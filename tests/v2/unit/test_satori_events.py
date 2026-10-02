from hyperot_adapter_satori.events import (
    SatoriBotOfflineEvent,
    SatoriBotOnlineEvent,
    SatoriChannelChangedEvent,
    SatoriCommandInteractionEvent,
    SatoriGuildChangedEvent,
    SatoriGuildEmojiChangedEvent,
    SatoriGuildRoleChangedEvent,
    SatoriInternalEvent,
    SatoriLoginChangedEvent,
    SatoriMessageReceivedEvent,
    SatoriMessageUpdatedEvent,
    translate_event,
)
from hyperot_adapter_satori.ids import decode_message_id, decode_request_id
from hyperot_adapter_satori.segments import SatoriSegmentCodec

from hyperot.v2.common import MemberRole, SceneType
from hyperot.v2.events import (
    BotOfflineEvent,
    BotOnlineEvent,
    FriendRequestedEvent,
    GroupInvitationReceivedEvent,
    GroupJoinRequestedEvent,
    GroupNameChangedEvent,
    MemberJoinedEvent,
    MemberLeftEvent,
    MemberRoleChangedEvent,
    MessageReactionChangedEvent,
    MessageRecalledEvent,
)
from hyperot.v2.messages import Quote

LOGIN = {"platform": "qq", "user": {"id": "10000", "nick": "bot"}, "status": 1}


def _event(event_type: str, **resources):
    return {"sn": 1, "type": event_type, "timestamp": 1700000000000, "login": LOGIN, **resources}


def _translate(payload: dict):
    return translate_event(payload, SatoriSegmentCodec())


CHANNEL = {"id": "chan1", "type": 0, "name": "general"}
GUILD = {"id": "guild1", "name": "group"}
DIRECT = {"id": "direct1", "type": 1}


def test_message_created_in_a_guild_channel():
    event = _translate(
        _event(
            "message-created",
            channel=CHANNEL,
            guild=GUILD,
            user={"id": "20001", "nick": "someone"},
            member={"user": {"id": "20001"}, "nick": "card", "roles": [{"id": "r1", "name": "admin"}]},
            message={"id": "msg1", "content": 'hi <at id="10000"/>'},
        )
    )
    assert isinstance(event, SatoriMessageReceivedEvent)
    assert (event.scene_type, event.scene_id) == (SceneType.GUILD, "chan1")
    assert (event.guild_id, event.channel_id) == ("guild1", "chan1")
    assert event.user_id == "20001"
    assert decode_message_id(event.message_id) == ("chan1", "msg1")
    assert str(event.message) == "hi @10000"
    assert event.is_mentioned
    assert event.sender.display_name == "card"
    assert event.sender.role == MemberRole.ADMIN


def test_message_created_in_a_private_channel():
    event = _translate(
        _event(
            "message-created",
            channel=DIRECT,
            user={"id": "20002"},
            message={"id": "msg2", "content": "hello"},
        )
    )
    assert (event.scene_type, event.scene_id) == (SceneType.USER, "20002")
    assert event.guild_id is None
    assert not event.is_mentioned


def test_message_created_mentions_everyone():
    event = _translate(
        _event(
            "message-created",
            channel=DIRECT,
            user={"id": "20002"},
            message={"id": "m", "content": '<at type="all"/>'},
        )
    )
    assert event.is_mentioned


def test_message_updated_keeps_the_message_fields():
    event = _translate(
        _event(
            "message-updated",
            channel=CHANNEL,
            guild=GUILD,
            user={"id": "20001"},
            message={"id": "msg1", "content": "edited"},
        )
    )
    assert isinstance(event, SatoriMessageUpdatedEvent)
    assert str(event.message) == "edited"


def test_quoted_message_ids_are_packed_with_the_channel():
    event = _translate(
        _event(
            "message-created",
            channel=CHANNEL,
            guild=GUILD,
            user={"id": "20001"},
            message={"id": "msg2", "content": '<quote id="msg1"/>hello'},
        )
    )
    quote = event.message[0]
    assert isinstance(quote, Quote) and quote.message_id == "chan1:msg1"


def test_message_deleted():
    event = _translate(
        _event(
            "message-deleted",
            channel=CHANNEL,
            guild=GUILD,
            user={"id": "20001"},
            operator={"id": "30003"},
            message={"id": "msg1"},
        )
    )
    assert isinstance(event, MessageRecalledEvent)
    assert event.operator_id == "30003"
    assert decode_message_id(event.message_id) == ("chan1", "msg1")


def test_reaction_events():
    added = _translate(
        _event(
            "reaction-added",
            channel=CHANNEL,
            guild=GUILD,
            user={"id": "20001"},
            message={"id": "msg1"},
            emoji={"id": "e1", "name": "thumbsup"},
        )
    )
    assert isinstance(added, MessageReactionChangedEvent)
    assert added.added and added.reaction.value == "thumbsup"
    removed = _translate(
        _event(
            "reaction-removed",
            channel=CHANNEL,
            guild=GUILD,
            user={"id": "20001"},
            message={"id": "msg1"},
            emoji={"id": "e1"},
        )
    )
    assert not removed.added and removed.reaction.value == "e1"


def test_guild_member_added_and_removed():
    joined = _translate(
        _event("guild-member-added", guild=GUILD, user={"id": "20001"}, member={"user": {"id": "20001"}})
    )
    assert isinstance(joined, MemberJoinedEvent)
    assert (joined.scene_type, joined.scene_id, joined.member_id) == (SceneType.GROUP, "guild1", "20001")

    left = _translate(
        _event(
            "guild-member-removed",
            guild=GUILD,
            user={"id": "20001"},
            operator={"id": "10000"},
        )
    )
    assert isinstance(left, MemberLeftEvent)
    assert left.kicked and left.operator_id == "10000"


def test_guild_member_updated_reports_the_current_role():
    event = _translate(
        _event(
            "guild-member-updated",
            guild=GUILD,
            user={"id": "20001"},
            member={"user": {"id": "20001"}, "roles": [{"id": "r1", "name": "owner"}]},
        )
    )
    assert isinstance(event, MemberRoleChangedEvent)
    # The protocol reports the roles a member has now, never the old ones.
    assert event.old_role is None and event.new_role == MemberRole.OWNER


def test_guild_member_request_packs_the_request_id():
    event = _translate(
        _event(
            "guild-member-request",
            guild=GUILD,
            user={"id": "20001"},
            message={"id": "req1", "content": "let me in"},
        )
    )
    assert isinstance(event, GroupJoinRequestedEvent)
    assert event.comment == "let me in"
    assert decode_request_id(event.request_id) == ("member", "guild1", "req1")


def test_guild_request_packs_the_request_id():
    event = _translate(
        _event("guild-request", guild=GUILD, user={"id": "20001"}, message={"id": "req2"})
    )
    assert isinstance(event, GroupInvitationReceivedEvent)
    assert event.inviter_id == "20001"
    assert decode_request_id(event.request_id) == ("guild", "guild1", "req2")


def test_friend_request_packs_the_request_id():
    event = _translate(_event("friend-request", user={"id": "20001"}, message={"id": "req3"}))
    assert isinstance(event, FriendRequestedEvent)
    assert decode_request_id(event.request_id) == ("friend", "", "req3")


def test_guild_updated_becomes_a_group_rename():
    event = _translate(_event("guild-updated", guild={**GUILD, "name": "new"}, operator={"id": "10000"}))
    assert isinstance(event, GroupNameChangedEvent)
    assert event.new_name == "new" and event.old_name is None


def test_guild_added_and_removed():
    added = _translate(_event("guild-added", guild=GUILD))
    assert isinstance(added, SatoriGuildChangedEvent) and added.change == "added"
    removed = _translate(_event("guild-removed", guild=GUILD))
    assert isinstance(removed, SatoriGuildChangedEvent) and removed.change == "removed"


def test_channel_events():
    event = _translate(_event("channel-updated", channel=CHANNEL, guild=GUILD))
    assert isinstance(event, SatoriChannelChangedEvent)
    assert (event.change, event.channel_name, event.guild_id) == ("updated", "general", "guild1")
    assert (event.scene_type, event.scene_id) == (SceneType.GUILD, "chan1")


def test_role_and_emoji_events():
    role = _translate(_event("guild-role-created", guild=GUILD, role={"id": "r1", "name": "admin"}))
    assert isinstance(role, SatoriGuildRoleChangedEvent)
    assert (role.change, role.role_id, role.role_name) == ("created", "r1", "admin")
    emoji = _translate(_event("guild-emoji-deleted", guild=GUILD, emoji={"id": "e1", "name": "smile"}))
    assert isinstance(emoji, SatoriGuildEmojiChangedEvent)
    assert (emoji.change, emoji.emoji_name) == ("deleted", "smile")


def test_login_events():
    online = _translate(_event("login-added", login=LOGIN))
    assert isinstance(online, BotOnlineEvent)
    assert isinstance(online, SatoriBotOnlineEvent)
    assert (online.platform, online.self_id) == ("qq", "10000")

    offline = _translate(_event("login-removed", login={**LOGIN, "status": 0, "user": None}))
    assert isinstance(offline, BotOfflineEvent)
    assert isinstance(offline, SatoriBotOfflineEvent)

    changed = _translate(_event("login-updated", login={**LOGIN, "status": 4}))
    assert isinstance(changed, SatoriLoginChangedEvent)
    assert changed.status == 4


def test_interaction_events():
    button = _translate(_event("interaction/button", channel=DIRECT, user={"id": "20001"}, button={"id": "b1"}))
    assert (button.button_id, button.platform, button.self_id) == ("b1", "qq", "10000")
    assert type(button).__name__ == "SatoriButtonInteractionEvent"

    command = _translate(
        _event(
            "interaction/command",
            channel=DIRECT,
            user={"id": "20001"},
            argv={"name": "ping", "arguments": ["a"], "options": {"x": 1}},
        )
    )
    assert isinstance(command, SatoriCommandInteractionEvent)
    assert (command.name, command.arguments, command.options) == ("ping", ["a"], {"x": 1})


def test_internal_event():
    event = _translate(_event("internal", _type="native.event", _data={"k": 1}))
    assert isinstance(event, SatoriInternalEvent)
    assert (event.event_type, event.data) == ("native.event", {"k": 1})


def test_unknown_event_type_is_ignored():
    assert _translate(_event("something-new")) is None
