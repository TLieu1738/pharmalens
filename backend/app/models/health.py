from typing import Literal

from pydantic import BaseModel

CheckState = Literal["configured", "missing"]


class RootResponse(BaseModel):
    name: str
    status: Literal["running"]
    version: str


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    environment: str
    version: str
    checks: dict[str, CheckState]
    storage: Literal["durable", "in_memory"]
