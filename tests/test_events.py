import pytest

from hyperot.events import (
    BotOnLineEvent,
    FriendAddEvent,
    FriendAddRequestEvent,
    FriendFileUploadEvent,
    FriendRecallEvent,
    GroupAddInviteEvent,
    GroupEssenceEvent,
    GroupFileUploadEvent,
    GroupInvitationEvent,
    GroupMemberDecreaseEvent,
    GroupMessageEvent,
    GroupMuteEvent,
    GroupNameChangeEvent,
    GroupRecallEvent,
    GroupWholeMuteEvent,
    MessageReactionEvent,
    NotifyEvent,
    PrivateMessageEvent,
    UnrecognizedEvent,
    em,
)


def _msg(post_type: str, event_type: str, **extra) -> dict:
    data = {
        "time": 1,
        "self_id": 2,
        "post_type": post_type,
        "user_id": 3,
        "group_id": 4,
        "message": [{"type": "text", "data": {"text": "hi"}}],
        "sender": {"user_id": 3, "nickname": "nick"},
        f"{post_type}_type": event_type,
    }
    data.update(extra)
    return data


@pytest.mark.parametrize(
    ("post_type", "event_type", "expected", "extra"),
    [
        ("message", "group", GroupMessageEvent, {}),
        ("message", "private", PrivateMessageEvent, {}),
        ("notice", "group_upload", GroupFileUploadEvent, {"file": {}}),
        ("notice", "group_decrease", GroupMemberDecreaseEvent, {"operator_id": 1}),
        ("notice", "group_ban", GroupMuteEvent, {"operator_id": 1, "duration": 60}),
        ("notice", "group_whole_mute", GroupWholeMuteEvent, {"operator_id": 1}),
        ("notice", "friend_add", FriendAddEvent, {}),
        ("notice", "group_recall", GroupRecallEvent, {"operator_id": 1, "message_id": "1"}),
        ("notice", "friend_recall", FriendRecallEvent, {"message_id": "1"}),
        ("notice", "notify", NotifyEvent, {"sub_type": "poke", "target_id": 5}),
        ("notice", "essence", GroupEssenceEvent, {"sender_id": 3, "operator_id": 2, "message_id": "9"}),
        (
            "notice",
            "reaction",
            MessageReactionEvent,
            {"message_id": "9", "operator_id": 2, "code": 1, "count": 2},
        ),
        ("notice", "bot_online", BotOnLineEvent, {"reason": "x"}),
        ("notice", "group_name_change", GroupNameChangeEvent, {"new_group_name": "new", "operator_id": 1}),
        ("notice", "group_invitation", GroupInvitationEvent, {"invitation_seq": 3, "initiator_id": 5}),
        ("notice", "friend_upload", FriendFileUploadEvent, {"file": {"id": "f1", "name": "a.txt", "size": 10}}),
        ("request", "friend", FriendAddRequestEvent, {"comment": "", "flag": "f"}),
        ("request", "group", GroupAddInviteEvent, {"comment": "", "flag": "f"}),
    ],
)
def test_event_classification(post_type, event_type, expected, extra):
    assert isinstance(em.new(_msg(post_type, event_type, **extra)), expected)


def test_message_event_preserves_sender_and_message():
    event = em.new(_msg("message", "group"))

    assert str(event.message) == "hi"
    assert event.group_id == 4
    assert event.user_id == 3
    assert event.sender.nickname == "nick"


def test_unknown_event_is_preserved():
    event = em.new({"time": 1, "post_type": "message", "message_type": "unknown", "message": [], "user_id": 3})

    assert isinstance(event, UnrecognizedEvent)
