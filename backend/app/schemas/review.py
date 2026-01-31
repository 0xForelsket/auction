from pydantic import BaseModel


class OverrideCreate(BaseModel):
    field_name: str
    new_value: str | None = None
    reason: str | None = None


class VerifyRequest(BaseModel):
    verified: bool = True
