from __future__ import annotations
from typing import Literal, Optional
from pydantic import BaseModel, Field


class ToolCall(BaseModel):
    step: int
    tool: str
    input: str
    output_summary: str
    timestamp: Optional[str] = None
    success: bool = True


class DiffEntry(BaseModel):
    step: int
    files_changed: list[str] = Field(default_factory=list)
    lines_added: int = 0
    lines_removed: int = 0
    reason: str = ""
    is_wasted: bool = False
    is_intentional_pivot: bool = False


class TraceStep(BaseModel):
    step: int
    goal: str = ""
    files_read: list[str] = Field(default_factory=list)
    files_modified: list[str] = Field(default_factory=list)
    tools_used: list[str] = Field(default_factory=list)
    decision: str = ""
    result: str = ""
    next_plan: str = ""
    phase: Literal["BUILD", "DEBUG", "VERIFY", "PLAN", "MAINTAIN", "FAILED", "SCAFFOLD"] = "BUILD"


class UserIntervention(BaseModel):
    step: int
    prompt: str
    type: Literal["positive", "negative"]
    reason: str = ""


class SessionMeta(BaseModel):
    harness_version: str = "1.0"
    model: str = "unknown"
    project: str = "unknown"
    date: str = ""
    total_time_minutes: Optional[float] = None
    build_success: bool = True
    test_pass_rate: Optional[float] = None
    task_prompt: str = ""
    user_interventions: list[UserIntervention] = Field(default_factory=list)


class HarnessInput(BaseModel):
    trace: list[TraceStep]
    tool_calls: list[ToolCall]
    diffs: list[DiffEntry]
    meta: SessionMeta


class MetricBreakdown(BaseModel):
    completion: float
    efficiency: float
    tool_success: float
    recovery: float
    diff_quality: float
    planning_quality: float
    composite: float

    completion_detail: str = ""
    efficiency_detail: str = ""
    tool_success_detail: str = ""
    recovery_detail: str = ""
    diff_quality_detail: str = ""
    planning_quality_detail: str = ""


class HarnessResult(BaseModel):
    project: str
    model: str
    date: str
    score: float
    grade: str
    metrics: MetricBreakdown
    total_steps: int
    productive_steps: int
    total_tool_calls: int
    failed_tool_calls: int
    lines_added: int
    lines_removed: int
    wasted_lines: int
    negative_interventions: int
    positive_interventions: int
