from enum import StrEnum


class SceneType(StrEnum):
    USER = "user"
    GROUP = "group"
    GUILD = "guild"


class MemberRole(StrEnum):
    MEMBER = "member"
    ADMIN = "admin"
    OWNER = "owner"


class UserSex(StrEnum):
    MALE = "male"
    FEMALE = "female"
    UNKNOWN = "unknown"


class ReactionKind(StrEnum):
    FACE = "face"
    EMOJI = "emoji"
