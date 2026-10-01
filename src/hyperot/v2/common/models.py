from pydantic import BaseModel, ConfigDict

from .enums import MemberRole, ReactionKind, UserSex


class FileInfo(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    file_id: str
    name: str
    size: int


class UserSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    user_id: str
    nick_name: str | None = None
    display_name: str | None = None
    sex: UserSex | None = None
    role: MemberRole | None = None
    title: str | None = None


class ReactionValue(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    kind: ReactionKind
    value: str
