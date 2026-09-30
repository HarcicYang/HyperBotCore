from pydantic import BaseModel, ConfigDict, Field


class AdapterManifest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    schema_version: int = 1
    id: str
    name: str
    package: str
    version: str
    api_version: int
    requires_hyperot: str
    entrypoint: str
    protocol: str
    platforms: list[str] = Field(default_factory=list)

    @property
    def entrypoint_module(self) -> str:
        return self.entrypoint.split(":", 1)[0]

    @property
    def entrypoint_attr(self) -> str:
        return self.entrypoint.split(":", 1)[1]
