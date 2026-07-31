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


def _msg(post_type: str, msg_type: str, **extra) -> dict:
    data = {
        "time": 1,
        "self_id": 2,
        "post_type": post_type,
        "user_id": 3,
        "group_id": 4,
        "message": [{"type": "text", "data": {"text": "hi"}}],
        "sender": {"user_id": 3, "nickname": "nick"},
        f"{post_type}_type": msg_type,
    }
    data.update(extra)
    return data


def test_group_message_event():
    ev = em.new(_msg("message", "group"))
    assert isinstance(ev, GroupMessageEvent)
    assert str(ev.message) == "hi"
    assert ev.group_id == 4
    assert ev.user_id == 3
    assert ev.sender.nickname == "nick"


def test_private_message_event():
    ev = em.new(_msg("message", "private"))
    assert isinstance(ev, PrivateMessageEvent)
    assert str(ev.message) == "hi"


def test_notice_events():
    assert isinstance(em.new(_msg("notice", "group_upload", file={})), GroupFileUploadEvent)
    assert isinstance(em.new(_msg("notice", "group_decrease", operator_id=1)), GroupMemberDecreaseEvent)
    assert isinstance(em.new(_msg("notice", "group_ban", operator_id=1, duration=60)), GroupMuteEvent)
    assert isinstance(em.new(_msg("notice", "friend_add")), FriendAddEvent)
    assert isinstance(em.new(_msg("notice", "group_recall", operator_id=1, message_id="1")), GroupRecallEvent)
    assert isinstance(em.new(_msg("notice", "friend_recall", message_id="1")), FriendRecallEvent)
    assert isinstance(em.new(_msg("notice", "notify", sub_type="poke", target_id=5)), NotifyEvent)
    assert isinstance(em.new(_msg("notice", "essence", sender_id=3, operator_id=2, message_id="9")), GroupEssenceEvent)
    assert isinstance(
        em.new(_msg("notice", "reaction", message_id="9", operator_id=2, code=1, count=2)),
        MessageReactionEvent,
    )
    assert isinstance(em.new(_msg("notice", "bot_online", reason="x")), BotOnLineEvent)


def test_request_events():
    assert isinstance(em.new(_msg("request", "friend", comment="", flag="f")), FriendAddRequestEvent)
    assert isinstance(em.new(_msg("request", "group", comment="", flag="f")), GroupAddInviteEvent)


def test_unrecognized_event():
    ev = em.new({"time": 1, "post_type": "message", "message_type": "unknown", "message": [], "user_id": 3})
    assert isinstance(ev, UnrecognizedEvent)


def test_group_whole_mute_event():
    ev = em.new(_msg("notice", "group_whole_mute", sub_type="mute", operator_id=1))
    assert isinstance(ev, GroupWholeMuteEvent)
    assert ev.sub_type == "mute"
    assert ev.operator_id == 1


def test_group_name_change_event():
    ev = em.new(_msg("notice", "group_name_change", new_group_name="新群名", operator_id=1))
    assert isinstance(ev, GroupNameChangeEvent)
    assert ev.new_group_name == "新群名"
    assert ev.operator_id == 1


def test_group_invitation_event():
    ev = em.new(_msg("notice", "group_invitation", invitation_seq=3, initiator_id=5, source_group_id=6))
    assert isinstance(ev, GroupInvitationEvent)
    assert ev.invitation_seq == 3
    assert ev.initiator_id == 5
    assert ev.source_group_id == 6


def test_friend_file_upload_event():
    ev = em.new(_msg("notice", "friend_upload", file={"id": "f1", "name": "a.txt", "size": 10}))
    assert isinstance(ev, FriendFileUploadEvent)
    assert ev.file is not None
    assert ev.file["name"] == "a.txt"
