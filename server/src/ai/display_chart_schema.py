from __future__ import annotations

import pydantic

from src.ai.pulselang_parser import validate_pulselang


class DisplayChartVariableArgs(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid", populate_by_name=True)

    variable: str
    alias: str | None = None
    color: str | None = None
    display_type: str | None = pydantic.Field(
        default=None,
        validation_alias=pydantic.AliasChoices("display_type", "displayType"),
    )
    resolution: str | None = None
    roll_up: str | None = pydantic.Field(
        default=None,
        validation_alias=pydantic.AliasChoices("roll_up", "rollUp"),
    )
    use_right_axis: bool = pydantic.Field(
        default=False,
        validation_alias=pydantic.AliasChoices("use_right_axis", "useRightAxis"),
    )


class DisplayChartArgs(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid")

    chart_id: str | None = None
    name: str | None = None
    description: str | None = None
    chart_derived_from: str | None = None
    program: str | None = None
    variables: list[DisplayChartVariableArgs] | None = None
    format_y_as_duration_ms: bool = False
    interpolate_to_latest: bool = False
    cut_future_datapoints: bool = False
    default_zoom_window: str | None = None

    @pydantic.model_validator(mode="after")
    def validate_requirements(self) -> "DisplayChartArgs":
        if self.chart_id:
            return self
        if not self.name or not self.program or self.variables is None:
            raise ValueError("When not providing chart_id, name, program, and variables are required")
        return self

    @pydantic.field_validator("program")
    @classmethod
    def validate_program(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if not value.strip():
            raise ValueError("Chart program must be non-empty")
        validate_pulselang(value)
        return value
