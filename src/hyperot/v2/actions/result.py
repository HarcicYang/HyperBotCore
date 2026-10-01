from pydantic import BaseModel, ConfigDict, JsonValue
from typing_extensions import override

from ..common import FileId, GroupId, MemberRole, MessageId, UserId
from ..messages import Message
from .formatting import format_actor, format_message, format_text, format_url, format_value


class ResultModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    def log_summary(self) -> str:
        return type(self).__name__


class SendResult(ResultModel):
    message_id: MessageId

    @override
    def log_summary(self) -> str:
        return f"sent {format_text(str(self.message_id))}"


class UserProfile(ResultModel):
    user_id: UserId
    display_name: str | None = None
    sex: str | None = None
    age: int | None = None

    @override
    def log_summary(self) -> str:
        details = []
        if self.sex:
            details.append(f"sex={format_text(self.sex)}")
        if self.age is not None:
            details.append(f"age={self.age}")
        suffix = f" ({', '.join(details)})" if details else ""
        return f"{format_actor(self.user_id)} {format_text(self.display_name)}{suffix}"


class FriendInfo(ResultModel):
    user_id: UserId
    display_name: str | None = None

    @override
    def log_summary(self) -> str:
        return f"{format_actor(self.user_id)} {format_text(self.display_name)}"


class GroupProfile(ResultModel):
    group_id: GroupId
    name: str
    member_count: int | None = None
    max_member_count: int | None = None

    @override
    def log_summary(self) -> str:
        members = ""
        if self.member_count is not None:
            members = (
                f" ({self.member_count}/{self.max_member_count})"
                if self.max_member_count
                else f" ({self.member_count})"
            )
        return f"group {format_text(str(self.group_id))} {format_text(self.name)}{members}"


class GroupMemberProfile(ResultModel):
    group_id: GroupId
    user_id: UserId
    display_name: str | None = None
    card: str | None = None
    role: MemberRole | None = None

    @override
    def log_summary(self) -> str:
        name = self.card or self.display_name
        details = [f"group={format_text(str(self.group_id))}"]
        if self.role is not None:
            details.append(f"role={format_value(self.role)}")
        return f"{format_actor(self.user_id)} {format_text(name)} ({', '.join(details)})"


class FileUrl(ResultModel):
    url: str

    @override
    def log_summary(self) -> str:
        return f"url {format_url(self.url)}"


class BotProfile(ResultModel):
    user_id: UserId
    display_name: str

    @override
    def log_summary(self) -> str:
        return f"{format_actor(self.user_id)} {format_text(self.display_name)}"


class BotStatus(ResultModel):
    online: bool
    good: bool = True
    app_good: bool = True
    memory: int = 0

    @override
    def log_summary(self) -> str:
        return (
            f"online={format_value(self.online)} good={format_value(self.good)}"
            f" app_good={format_value(self.app_good)} memory={self.memory}"
        )


class VersionInfo(ResultModel):
    app_name: str
    app_version: str
    protocol_version: str

    @override
    def log_summary(self) -> str:
        return (
            f"{format_text(self.app_name)} {format_text(self.app_version)}"
            f" (protocol {format_text(self.protocol_version)})"
        )


class CookieInfo(ResultModel):
    cookies: str

    @override
    def log_summary(self) -> str:
        return f"cookie (length={len(self.cookies)})"


class CsrfTokenInfo(ResultModel):
    token: int

    @override
    def log_summary(self) -> str:
        return "csrf token"


class RawResult(ResultModel):
    data: JsonValue = None

    @override
    def log_summary(self) -> str:
        return f"raw {type(self.data).__name__}"


class FileReference(ResultModel):
    file_id: FileId
    name: str | None = None
    url: str | None = None

    @override
    def log_summary(self) -> str:
        name = self.name or str(self.file_id)
        details = [f"id={format_text(str(self.file_id))}"]
        if self.url:
            details.append(f"url={format_url(self.url)}")
        return f"file {format_text(name)} ({', '.join(details)})"


def format_result(result: object) -> str:
    if result is None:
        return "ok"
    if isinstance(result, ResultModel):
        return result.log_summary()
    if isinstance(result, Message):
        return f"message: {format_message(result)}"
    if isinstance(result, list | tuple):
        return f"{len(result)} items"
    return type(result).__name__
