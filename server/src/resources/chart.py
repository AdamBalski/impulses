from __future__ import annotations

from typing import Any

import fastapi
import pydantic

from src.auth import user_auth
from src.common import state
from src.dao.chart_repo import Chart, ChartRepo

router = fastapi.APIRouter()


class ChartBody(pydantic.BaseModel):
    name: str
    description: str = ""
    program: str
    variables: list[dict[str, Any]] = pydantic.Field(default_factory=list)
    format_y_as_duration_ms: bool = False
    interpolate_to_latest: bool = False
    cut_future_datapoints: bool = False
    default_zoom_window: str | None = None


class ChartDto(ChartBody):
    id: str
    created_at: int
    updated_at: int


def _to_dto(chart: Chart) -> ChartDto:
    return ChartDto(
        id=chart.id,
        name=chart.name,
        description=chart.description,
        program=chart.program,
        variables=chart.variables,
        format_y_as_duration_ms=chart.format_y_as_duration_ms,
        interpolate_to_latest=chart.interpolate_to_latest,
        cut_future_datapoints=chart.cut_future_datapoints,
        default_zoom_window=chart.default_zoom_window,
        created_at=chart.created_at,
        updated_at=chart.updated_at,
    )


@router.get("", response_model=list[ChartDto])
@router.get("/", response_model=list[ChartDto])
async def list_charts(
    repo: ChartRepo = state.injected(ChartRepo),
    u=fastapi.Depends(user_auth.get_current_user),
) -> list[ChartDto]:
    return [_to_dto(chart) for chart in repo.list_charts(u.id)]


@router.get("/{chart_id}", response_model=ChartDto)
async def get_chart(
    chart_id: str,
    repo: ChartRepo = state.injected(ChartRepo),
    u=fastapi.Depends(user_auth.get_current_user),
) -> ChartDto:
    chart = repo.get_chart_by_id(u.id, chart_id)
    if not chart:
        raise fastapi.HTTPException(status_code=404, detail="Chart not found")
    return _to_dto(chart)


@router.post("", response_model=ChartDto)
@router.post("/", response_model=ChartDto)
async def create_chart(
    body: ChartBody,
    repo: ChartRepo = state.injected(ChartRepo),
    u=fastapi.Depends(user_auth.get_current_user),
) -> ChartDto:
    chart = repo.create_chart(
        user_id=u.id,
        name=body.name,
        description=body.description,
        program=body.program,
        variables=body.variables,
        format_y_as_duration_ms=body.format_y_as_duration_ms,
        interpolate_to_latest=body.interpolate_to_latest,
        cut_future_datapoints=body.cut_future_datapoints,
        default_zoom_window=body.default_zoom_window,
    )
    return _to_dto(chart)


@router.put("/{chart_id}", response_model=ChartDto)
async def update_chart(
    chart_id: str,
    body: ChartBody,
    repo: ChartRepo = state.injected(ChartRepo),
    u=fastapi.Depends(user_auth.get_current_user),
) -> ChartDto:
    chart = repo.update_chart(
        user_id=u.id,
        chart_id=chart_id,
        name=body.name,
        description=body.description,
        program=body.program,
        variables=body.variables,
        format_y_as_duration_ms=body.format_y_as_duration_ms,
        interpolate_to_latest=body.interpolate_to_latest,
        cut_future_datapoints=body.cut_future_datapoints,
        default_zoom_window=body.default_zoom_window,
    )
    if not chart:
        raise fastapi.HTTPException(status_code=404, detail="Chart not found")
    return _to_dto(chart)


@router.delete("/{chart_id}")
async def delete_chart(
    chart_id: str,
    repo: ChartRepo = state.injected(ChartRepo),
    u=fastapi.Depends(user_auth.get_current_user),
) -> None:
    chart = repo.get_chart_by_id(u.id, chart_id)
    if not chart:
        raise fastapi.HTTPException(status_code=404, detail="Chart not found")
    repo.delete_chart(u.id, chart_id)
    return None
