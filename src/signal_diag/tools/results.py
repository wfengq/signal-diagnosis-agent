"""Tool execution results with status invariants."""

from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .contracts import ToolName
from .evidence import Evidence

ToolStatus = Literal["success", "invalid", "error"]

T = TypeVar("T")


class ToolResult(BaseModel, Generic[T]):
    model_config = ConfigDict(frozen=True)

    call_id: str = Field(pattern=r"^call_")
    tool_name: ToolName
    status: ToolStatus
    result: T | None = None
    evidence: tuple[Evidence, ...] = ()
    warnings: tuple[str, ...] = ()
    error_message: str | None = None

    @model_validator(mode="after")
    def validate_status_invariants(self) -> "ToolResult[T]":
        if self.status == "success":
            if self.result is None:
                raise ValueError("success ToolResult requires a result")
            if self.error_message is not None:
                raise ValueError("success ToolResult must not include error_message")
        elif self.status == "invalid":
            if not self.warnings:
                raise ValueError("invalid ToolResult requires non-empty warnings")
            if self.error_message is not None:
                raise ValueError("invalid ToolResult must not include error_message")
        elif self.status == "error":
            if self.result is not None:
                raise ValueError("error ToolResult must not include a result")
            if self.evidence:
                raise ValueError("error ToolResult must not include evidence")
            if self.error_message is None:
                raise ValueError("error ToolResult requires error_message")
        return self
