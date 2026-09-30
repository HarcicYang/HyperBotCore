from pydantic import BaseModel, ConfigDict

from .enums import MemberRole, ReactionKind, UserSex
from .ids import FileId, UserId


class FileInfo(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    file_id: FileId
    name: str
    size: int


class UserSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    user_id: UserId
    nick_name: str | None = None
    display_name: str | None = None
    sex: UserSex | None = None
    role: MemberRole | None = None
    title: str | None = None


class ReactionValue(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    kind: ReactionKind
    value: str
