from hyperot_adapter_onebot.events import (
    OneBotFileUploadedEvent,
    OneBotHeartbeatEvent,
    OneBotLifecycleEvent,
    OneBotMessageReceivedEvent,
    OneBotPokeReceivedEvent,
    translate_event,
)
from hyperot_adapter_onebot.segments import OneBotSegmentCodec

from hyperot.v2.common import ReactionKind, UserSex
from hyperot.v2.events import (
    GroupInvitationReceivedEvent,
    GroupJoinRequestedEvent,
    MemberLeftEvent,
    MessageReactionChangedEvent,
)
from hyperot.v2.messages import MentionAll


def _event(post_type: str, **data):
    return {
        "time": 1,
        "self_id": 100,
        "post_type": post_type,
        **data,
    }


def test_message_event_preserves_sender_and_metadata():
    event = translate_event(
        _event(
            "message",
            message_type="group",
            sub_type="normal",
            message_id=7,
            group_id=10,
            user_id=20,
            raw_message="[CQ:at,qq=all]",
            font=1,
            message=[{"type": "at", "data": {"qq": "all"}}],
            sender={
                "user_id": 20,
                "nickname": "nick",
                "card": "display",
                "sex": "female",
                "role": "admin",
                "title": "title",
                "age": 18,
                "area": "area",
                "level": "9",
            },
        ),
        OneBotSegmentCodec(),
    )
    assert isinstance(event, OneBotMessageReceivedEvent)
    assert isinstance(event.message[0], MentionAll)
    assert event.is_mentioned is True
    assert event.sender is not None
    assert event.sender.nick_name == "nick"
    assert event.sender.display_name == "display"
    assert event.sender.sex is UserSex.FEMALE
    assert event.sender.role is not None
    assert event.sender.role.value == "admin"
    assert event.raw_message == "[CQ:at,qq=all]"
    assert event.sender_level == "9"


def test_notice_extensions_are_typed():
    codec = OneBotSegmentCodec()
    file_event = translate_event(
        _event(
            "notice",
            notice_type="group_upload",
            group_id=10,
            user_id=20,
            file={"id": "f", "name": "a.txt", "size": 3, "busid": 1},
        ),
        codec,
    )
    assert isinstance(file_event, OneBotFileUploadedEvent)
    assert file_event.busid == 1

    poke = translate_event(
        _event("notice", notice_type="notify", sub_type="poke", group_id=10, user_id=20, target_id=100),
        codec,
    )
    assert isinstance(poke, OneBotPokeReceivedEvent)
    assert str(poke.target_id) == "100"


def test_request_and_meta_events_are_split():
    codec = OneBotSegmentCodec()
    join = translate_event(
        _event(
            "request",
            request_type="group",
            sub_type="add",
            group_id=10,
            user_id=20,
            comment="hello",
            flag="flag",
        ),
        codec,
    )
    assert isinstance(join, GroupJoinRequestedEvent)

    invite = translate_event(
        _event("request", request_type="group", sub_type="invite", group_id=10, user_id=20, flag="flag"),
        codec,
    )
    assert isinstance(invite, GroupInvitationReceivedEvent)
    assert invite.request_id == "flag"

    lifecycle = translate_event(_event("meta_event", meta_event_type="lifecycle", sub_type="connect"), codec)
    assert isinstance(lifecycle, OneBotLifecycleEvent)

    heartbeat = translate_event(
        _event("meta_event", meta_event_type="heartbeat", interval=15000, status={"online": True, "good": True}),
        codec,
    )
    assert isinstance(heartbeat, OneBotHeartbeatEvent)
    assert heartbeat.status.online is True


def test_recall_reaction_mapping_keeps_typed_values():
    event = translate_event(
        _event(
            "notice",
            notice_type="reaction",
            group_id=10,
            user_id=20,
            message_id=7,
            code=123,
            reaction_type="emoji",
            sub_type="add",
            count=2,
        ),
        OneBotSegmentCodec(),
    )
    assert isinstance(event, MessageReactionChangedEvent)
    assert event.reaction.kind is ReactionKind.EMOJI
    assert event.reaction.value == "123"

    left = translate_event(
        _event(
            "notice",
            notice_type="group_decrease",
            sub_type="kick_me",
            group_id=10,
            user_id=100,
            operator_id=20,
        ),
        OneBotSegmentCodec(),
    )
    assert isinstance(left, MemberLeftEvent)
    assert left.kicked is True
    assert left.self_kicked is True
