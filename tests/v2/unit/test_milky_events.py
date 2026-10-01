from hyperot_adapter_milky.events import (
    MilkyFriendRequestedEvent,
    MilkyGroupDisbandedEvent,
    MilkyGroupInvitationReceivedEvent,
    MilkyGroupJoinRequestedEvent,
    MilkyMemberInviteRequestedEvent,
    MilkyMessageReceivedEvent,
    translate_event,
)
from hyperot_adapter_milky.segments import MilkySegmentCodec

from hyperot.v2.common import MemberRole, ReactionKind, ReactionValue, SceneType
from hyperot.v2.events import (
    BotOfflineEvent,
    EssenceChangedEvent,
    FileUploadedEvent,
    GroupMuteChangedEvent,
    GroupNameChangedEvent,
    MemberJoinedEvent,
    MemberLeftEvent,
    MemberMuteChangedEvent,
    MemberRoleChangedEvent,
    MessageReactionChangedEvent,
    MessageRecalledEvent,
    PokeReceivedEvent,
)


def _event(event_type: str, data: dict) -> dict:
    return {"time": 1700000000, "self_id": 10000, "event_type": event_type, "data": data}


def _translate(payload: dict):
    return translate_event(payload, MilkySegmentCodec())


GROUP_MESSAGE = _event(
    "message_receive",
    {
        "message_scene": "group",
        "peer_id": 12345,
        "message_seq": 456,
        "sender_id": 10001,
        "time": 1700000001,
        "segments": [
            {"type": "text", "data": {"text": "hi "}},
            {"type": "mention", "data": {"user_id": 10000, "name": "bot"}},
        ],
        "group": {"group_id": 12345, "group_name": "g", "member_count": 2, "max_member_count": 5},
        "group_member": {
            "user_id": 10001,
            "nickname": "nick",
            "sex": "male",
            "group_id": 12345,
            "card": "card",
            "title": "title",
            "level": 3,
            "role": "admin",
        },
    },
)


FRIEND_MESSAGE = _event(
    "message_receive",
    {
        "message_scene": "friend",
        "peer_id": 10001,
        "message_seq": 7,
        "sender_id": 10001,
        "time": 1700000002,
        "segments": [{"type": "text", "data": {"text": "yo"}}],
        "friend": {"user_id": 10001, "nickname": "friend", "sex": "female"},
    },
)


TEMP_MESSAGE = _event(
    "message_receive",
    {
        "message_scene": "temp",
        "peer_id": 12345,
        "message_seq": 8,
        "sender_id": 10001,
        "time": 1700000003,
        "segments": [{"type": "text", "data": {"text": "temp"}}],
    },
)


def test_group_message_event():
    event = _translate(GROUP_MESSAGE)

    assert isinstance(event, MilkyMessageReceivedEvent)
    assert event.scene_type is SceneType.GROUP
    assert event.scene_id == "12345"
    assert event.user_id == "10001"
    assert event.message_id == "group:12345:456"
    assert str(event.message) == "hi @10000"
    assert event.is_mentioned is True
    assert event.self_id == "10000"
    assert event.sender is not None
    assert event.sender.display_name == "card"
    assert event.sender.role is MemberRole.ADMIN


def test_friend_message_event():
    event = _translate(FRIEND_MESSAGE)

    assert isinstance(event, MilkyMessageReceivedEvent)
    assert event.scene_type is SceneType.USER
    assert event.scene_id == "10001"
    assert event.message_id == "friend:10001:7"
    assert event.is_mentioned is False


def test_temp_message_event_is_treated_as_private():
    event = _translate(TEMP_MESSAGE)

    assert event.scene_type is SceneType.USER
    assert event.scene_id == "10001"
    assert event.message_scene == "temp"
    assert event.message_id == "temp:12345:8"


def test_bot_offline_event():
    event = _translate(_event("bot_offline", {"reason": "kick"}))

    assert isinstance(event, BotOfflineEvent)
    assert event.reason == "kick"


def test_message_recall_event():
    event = _translate(
        _event(
            "message_recall",
            {
                "message_scene": "group",
                "peer_id": 12345,
                "message_seq": 456,
                "sender_id": 10001,
                "operator_id": 12345,
                "display_suffix": "suffix",
            },
        )
    )

    assert isinstance(event, MessageRecalledEvent)
    assert event.scene_id == "12345"
    assert event.message_id == "group:12345:456"
    assert event.operator_id == "12345"


def test_peer_pin_change_event():
    event = _translate(_event("peer_pin_change", {"message_scene": "friend", "peer_id": 10001, "is_pinned": True}))

    assert event.scene_type is SceneType.USER
    assert event.is_pinned is True


def test_member_events():
    joined = _translate(
        _event(
            "group_member_increase",
            {"group_id": 1, "user_id": 2, "operator_id": 3, "invitor_id": None},
        )
    )
    assert isinstance(joined, MemberJoinedEvent)
    assert joined.member_id == "2"
    assert joined.operator_id == "3"
    assert joined.inviter_id is None

    left = _translate(_event("group_member_decrease", {"group_id": 1, "user_id": 2, "operator_id": 3}))
    assert isinstance(left, MemberLeftEvent)
    assert left.kicked is True

    voluntary = _translate(_event("group_member_decrease", {"group_id": 1, "user_id": 2, "operator_id": None}))
    assert voluntary.kicked is False


def test_admin_and_essence_events():
    admin = _translate(_event("group_admin_change", {"group_id": 1, "user_id": 2, "operator_id": 3, "is_set": True}))
    assert isinstance(admin, MemberRoleChangedEvent)
    assert admin.new_role is MemberRole.ADMIN
    assert admin.member_id == "2"

    unset = _translate(_event("group_admin_change", {"group_id": 1, "user_id": 2, "is_set": False}))
    assert unset.new_role is MemberRole.MEMBER
    assert unset.operator_id is None

    essence = _translate(
        _event(
            "group_essence_message_change",
            {"group_id": 1, "message_seq": 9, "operator_id": 2, "is_set": True},
        )
    )
    assert isinstance(essence, EssenceChangedEvent)
    assert essence.message_id == "group:1:9"
    assert essence.added is True


def test_mute_events():
    mute = _translate(_event("group_mute", {"group_id": 1, "user_id": 2, "operator_id": 3, "duration": 60}))
    assert isinstance(mute, MemberMuteChangedEvent)
    assert mute.muted is True
    assert mute.duration == 60

    unmute = _translate(_event("group_mute", {"group_id": 1, "user_id": 2, "operator_id": 3, "duration": 0}))
    assert unmute.muted is False

    whole = _translate(_event("group_whole_mute", {"group_id": 1, "operator_id": 2, "is_mute": True}))
    assert isinstance(whole, GroupMuteChangedEvent)
    assert whole.muted is True


def test_group_metadata_events():
    renamed = _translate(_event("group_name_change", {"group_id": 1, "new_group_name": "new", "operator_id": 2}))
    assert isinstance(renamed, GroupNameChangedEvent)
    assert renamed.new_name == "new"
    assert renamed.old_name is None

    disbanded = _translate(_event("group_disband", {"group_id": 1, "operator_id": 2}))
    assert isinstance(disbanded, MilkyGroupDisbandedEvent)
    assert disbanded.operator_id == "2"


def test_reaction_event():
    event = _translate(
        _event(
            "group_message_reaction",
            {
                "group_id": 1,
                "user_id": 2,
                "message_seq": 9,
                "face_id": "128",
                "reaction_type": "face",
                "is_add": True,
            },
        )
    )

    assert isinstance(event, MessageReactionChangedEvent)
    assert event.message_id == "group:1:9"
    assert event.reaction == ReactionValue(kind=ReactionKind.FACE, value="128")
    assert event.added is True

    emoji = _translate(
        _event(
            "group_message_reaction",
            {"group_id": 1, "user_id": 2, "message_seq": 9, "face_id": "😀", "reaction_type": "emoji", "is_add": False},
        )
    )
    assert emoji.reaction.kind is ReactionKind.EMOJI
    assert emoji.added is False


def test_nudge_events():
    friend = _translate(
        _event(
            "friend_nudge",
            {
                "user_id": 2,
                "is_self_send": False,
                "is_self_receive": True,
                "display_action": "action",
                "display_suffix": "suffix",
                "display_action_img_url": "http://x/a.png",
            },
        )
    )
    assert isinstance(friend, PokeReceivedEvent)
    assert friend.scene_type is SceneType.USER
    assert friend.target_id == "10000"
    assert friend.display_action == "action"

    group = _translate(
        _event(
            "group_nudge",
            {
                "group_id": 1,
                "sender_id": 2,
                "receiver_id": 3,
                "display_action": "action",
                "display_suffix": "suffix",
                "display_action_img_url": "http://x/a.png",
            },
        )
    )
    assert group.user_id == "2"
    assert group.target_id == "3"


def test_file_upload_events():
    group_file = _translate(
        _event(
            "group_file_upload", {"group_id": 1, "user_id": 2, "file_id": "f1", "file_name": "a.zip", "file_size": 10}
        )
    )
    assert isinstance(group_file, FileUploadedEvent)
    assert group_file.scene_type is SceneType.GROUP
    assert group_file.file.file_id == "f1"
    assert group_file.file.size == 10

    friend_file = _translate(
        _event(
            "friend_file_upload",
            {"user_id": 2, "file_id": "f2", "file_name": "b.zip", "file_size": 20, "file_hash": "h", "is_self": True},
        )
    )
    assert friend_file.scene_type is SceneType.USER
    assert friend_file.file_hash == "h"
    assert friend_file.is_self is True


def test_request_events():
    friend = _translate(
        _event(
            "friend_request",
            {"initiator_id": 2, "initiator_uid": "uid-1", "comment": "hi", "via": "search"},
        )
    )
    assert isinstance(friend, MilkyFriendRequestedEvent)
    assert friend.request_id == "uid-1"
    assert friend.initiator_id == "2"
    assert friend.comment == "hi"

    join = _translate(
        _event(
            "group_join_request",
            {
                "group_id": 1,
                "notification_seq": 9,
                "is_filtered": True,
                "initiator_id": 2,
                "comment": "let me in",
            },
        )
    )
    assert isinstance(join, MilkyGroupJoinRequestedEvent)
    assert join.request_id == "group_request:1:9"
    assert join.notification_type == "join_request"
    assert join.is_filtered is True
    assert join.comment == "let me in"

    invited = _translate(
        _event(
            "group_invited_join_request",
            {
                "group_id": 1,
                "notification_seq": 10,
                "initiator_id": 2,
                "target_user_id": 3,
            },
        )
    )
    assert isinstance(invited, MilkyMemberInviteRequestedEvent)
    assert invited.request_id == "group_request:1:10"
    assert invited.target_user_id == "3"

    invitation = _translate(
        _event(
            "group_invitation",
            {"group_id": 1, "invitation_seq": 11, "initiator_id": 2, "source_group_id": 3},
        )
    )
    assert isinstance(invitation, MilkyGroupInvitationReceivedEvent)
    assert invitation.request_id == "group_invitation:1:11"
    assert invitation.source_group_id == "3"


def test_unknown_event_type_is_ignored():
    assert _translate(_event("some_future_event", {"x": 1})) is None


def test_unknown_segment_in_message_falls_back_to_text():
    event = _translate(
        _event(
            "message_receive",
            {
                "message_scene": "friend",
                "peer_id": 1,
                "message_seq": 1,
                "sender_id": 2,
                "segments": [{"type": "poke", "data": {"id": "1"}}],
            },
        )
    )

    assert str(event.message) == "[不支持的消息段: poke]"
