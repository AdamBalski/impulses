from __future__ import annotations

from typing import Any

import fastapi
import pydantic

from src.auth import user_auth
from src.common import state
from src.dao.chart_repo import ChartRepo
from src.dao.dashboard_repo import Dashboard, DashboardRepo

router = fastapi.APIRouter()


class DashboardBody(pydantic.BaseModel):
    name: str
    description: str = ""
    program: str = ""
    default_zoom_window: str | None = None
    override_chart_zoom: bool = False
    layout: list[dict[str, Any]] = pydantic.Field(default_factory=list)


class DashboardDto(DashboardBody):
    id: str
    created_at: int
    updated_at: int


class LocalImportChartBody(pydantic.BaseModel):
    local_id: str
    name: str
    description: str = ""
    program: str
    variables: list[dict[str, Any]] = pydantic.Field(default_factory=list)
    format_y_as_duration_ms: bool = False
    interpolate_to_latest: bool = False
    cut_future_datapoints: bool = False
    default_zoom_window: str | None = None
    created_at: int | None = None
    updated_at: int | None = None


class LocalImportDashboardBody(DashboardBody):
    local_id: str
    created_at: int | None = None
    updated_at: int | None = None


class ImportLocalBundleBody(pydantic.BaseModel):
    charts: list[LocalImportChartBody] = pydantic.Field(default_factory=list)
    dashboards: list[LocalImportDashboardBody] = pydantic.Field(default_factory=list)


class ImportLocalBundleResultDto(pydantic.BaseModel):
    charts_created: int
    dashboards_created: int
    chart_id_map: dict[str, str]
    dashboard_id_map: dict[str, str]


def _to_dto(dashboard: Dashboard) -> DashboardDto:
    return DashboardDto(
        id=dashboard.id,
        name=dashboard.name,
        description=dashboard.description,
        program=dashboard.program,
        default_zoom_window=dashboard.default_zoom_window,
        override_chart_zoom=dashboard.override_chart_zoom,
        layout=dashboard.layout,
        created_at=dashboard.created_at,
        updated_at=dashboard.updated_at,
    )


def _validate_layout_chart_ids(
    user_id: str,
    layout: list[dict[str, Any]],
    chart_repo: ChartRepo,
) -> None:
    for item in layout:
        chart_id = item.get("chartId")
        if not isinstance(chart_id, str) or not chart_id:
            raise fastapi.HTTPException(status_code=422, detail="Each dashboard layout item must include chartId")
        if not chart_repo.get_chart_by_id(user_id, chart_id):
            raise fastapi.HTTPException(status_code=422, detail=f"Referenced chart not found: {chart_id}")


@router.get("", response_model=list[DashboardDto])
@router.get("/", response_model=list[DashboardDto])
async def list_dashboards(
    repo: DashboardRepo = state.injected(DashboardRepo),
    u=fastapi.Depends(user_auth.get_current_user),
) -> list[DashboardDto]:
    return [_to_dto(dashboard) for dashboard in repo.list_dashboards(u.id)]


@router.get("/{dashboard_id}", response_model=DashboardDto)
async def get_dashboard(
    dashboard_id: str,
    repo: DashboardRepo = state.injected(DashboardRepo),
    u=fastapi.Depends(user_auth.get_current_user),
) -> DashboardDto:
    dashboard = repo.get_dashboard_by_id(u.id, dashboard_id)
    if not dashboard:
        raise fastapi.HTTPException(status_code=404, detail="Dashboard not found")
    return _to_dto(dashboard)


@router.post("", response_model=DashboardDto)
@router.post("/", response_model=DashboardDto)
async def create_dashboard(
    body: DashboardBody,
    repo: DashboardRepo = state.injected(DashboardRepo),
    chart_repo: ChartRepo = state.injected(ChartRepo),
    u=fastapi.Depends(user_auth.get_current_user),
) -> DashboardDto:
    _validate_layout_chart_ids(u.id, body.layout, chart_repo)
    dashboard = repo.create_dashboard(
        user_id=u.id,
        name=body.name,
        description=body.description,
        program=body.program,
        default_zoom_window=body.default_zoom_window,
        override_chart_zoom=body.override_chart_zoom,
        layout=body.layout,
    )
    return _to_dto(dashboard)


@router.put("/{dashboard_id}", response_model=DashboardDto)
async def update_dashboard(
    dashboard_id: str,
    body: DashboardBody,
    repo: DashboardRepo = state.injected(DashboardRepo),
    chart_repo: ChartRepo = state.injected(ChartRepo),
    u=fastapi.Depends(user_auth.get_current_user),
) -> DashboardDto:
    _validate_layout_chart_ids(u.id, body.layout, chart_repo)
    dashboard = repo.update_dashboard(
        user_id=u.id,
        dashboard_id=dashboard_id,
        name=body.name,
        description=body.description,
        program=body.program,
        default_zoom_window=body.default_zoom_window,
        override_chart_zoom=body.override_chart_zoom,
        layout=body.layout,
    )
    if not dashboard:
        raise fastapi.HTTPException(status_code=404, detail="Dashboard not found")
    return _to_dto(dashboard)


@router.delete("/{dashboard_id}")
async def delete_dashboard(
    dashboard_id: str,
    repo: DashboardRepo = state.injected(DashboardRepo),
    u=fastapi.Depends(user_auth.get_current_user),
) -> None:
    dashboard = repo.get_dashboard_by_id(u.id, dashboard_id)
    if not dashboard:
        raise fastapi.HTTPException(status_code=404, detail="Dashboard not found")
    repo.delete_dashboard(u.id, dashboard_id)
    return None


@router.post("/import-local-bundle", response_model=ImportLocalBundleResultDto)
async def import_local_bundle(
    body: ImportLocalBundleBody,
    chart_repo: ChartRepo = state.injected(ChartRepo),
    dashboard_repo: DashboardRepo = state.injected(DashboardRepo),
    u=fastapi.Depends(user_auth.get_current_user),
) -> ImportLocalBundleResultDto:
    chart_id_map: dict[str, str] = {}
    dashboard_id_map: dict[str, str] = {}

    for chart in body.charts:
        created = chart_repo.create_chart(
            user_id=u.id,
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
        chart_id_map[chart.local_id] = created.id

    for dashboard in body.dashboards:
        remapped_layout: list[dict[str, Any]] = []
        for item in dashboard.layout:
            chart_id = item.get("chartId")
            if not isinstance(chart_id, str) or chart_id not in chart_id_map:
                raise fastapi.HTTPException(
                    status_code=422,
                    detail=f"Dashboard {dashboard.local_id} references unknown local chart id: {chart_id}",
                )
            remapped_layout.append({
                **item,
                "chartId": chart_id_map[chart_id],
            })

        created = dashboard_repo.create_dashboard(
            user_id=u.id,
            name=dashboard.name,
            description=dashboard.description,
            program=dashboard.program,
            default_zoom_window=dashboard.default_zoom_window,
            override_chart_zoom=dashboard.override_chart_zoom,
            layout=remapped_layout,
            created_at=dashboard.created_at,
            updated_at=dashboard.updated_at,
        )
        dashboard_id_map[dashboard.local_id] = created.id

    return ImportLocalBundleResultDto(
        charts_created=len(chart_id_map),
        dashboards_created=len(dashboard_id_map),
        chart_id_map=chart_id_map,
        dashboard_id_map=dashboard_id_map,
    )
