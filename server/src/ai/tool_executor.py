from __future__ import annotations

import datetime
import json
from typing import Any

import fastapi
import pydantic

from src.ai.display_chart_schema import DisplayChartArgs
from src.dao.data_dao import DataDao
from src.dao.chart_repo import Chart, ChartRepo
from src.dao.dashboard_repo import Dashboard, DashboardRepo


class _NoArgs(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid")


class _ChartIdArgs(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid")
    chart_id: str


class _DashboardIdArgs(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid")
    dashboard_id: str


class _MetricNameArgs(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid")
    metric_name: str


TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "explain_pulselang",
            "description": "Explain what PulseLang is and summarize how it works in Impulses.",
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "display_chart",
            "description": "Display a chart visually in the UI. Pass a chart_id to display a saved chart exactly as is without modifying it. Pass a full chart payload (name, program, variables) when proposing a new or modified chart.",
            "parameters": {
                "type": "object",
                "properties": {
                    "chart_id": {
                        "type": "string",
                        "description": "UUID of the saved chart to display exactly as is. If provided, other fields are optional.",
                    },
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "chart_derived_from": {"type": "string"},
                    "program": {"type": "string"},
                    "variables": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "variable": {"type": "string"},
                                "alias": {"type": "string"},
                                "color": {"type": "string"},
                                "display_type": {"type": "string"},
                                "resolution": {"type": "string"},
                                "roll_up": {"type": "string"},
                                "use_right_axis": {"type": "boolean"},
                            },
                            "required": ["variable"],
                            "additionalProperties": False,
                        },
                    },
                    "format_y_as_duration_ms": {"type": "boolean"},
                    "interpolate_to_latest": {"type": "boolean"},
                    "cut_future_datapoints": {"type": "boolean"},
                    "default_zoom_window": {"type": "string"},
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "explain_chart_structure",
            "description": "Explain in natural language what fields and concepts make up an Impulses chart definition.",
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "explain_dashboard_structure",
            "description": "Explain in natural language what fields and concepts make up an Impulses dashboard definition.",
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_metric_names",
            "description": "List the user's metric names.",
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_metric_last_10_datapoints",
            "description": "Get the last 10 datapoints for one metric name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "metric_name": {
                        "type": "string",
                        "description": "Metric name to inspect.",
                    },
                },
                "required": ["metric_name"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_metric_summary",
            "description": "Get a summary of one metric including time range, point counts, dimensions, and value range.",
            "parameters": {
                "type": "object",
                "properties": {
                    "metric_name": {
                        "type": "string",
                        "description": "Metric name to summarize.",
                    },
                },
                "required": ["metric_name"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_metric_common_dimensions",
            "description": "Get the most common dimension maps used in a metric stream, along with total point count.",
            "parameters": {
                "type": "object",
                "properties": {
                    "metric_name": {
                        "type": "string",
                        "description": "Metric name to inspect.",
                    },
                },
                "required": ["metric_name"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_charts",
            "description": "List the user's saved charts with UUIDs and names.",
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_chart",
            "description": "Get one saved chart by UUID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "chart_id": {
                        "type": "string",
                        "description": "UUID of the chart to retrieve.",
                    },
                },
                "required": ["chart_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_dashboards",
            "description": "List the user's saved dashboards with UUIDs and names.",
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_dashboard",
            "description": "Get one saved dashboard by UUID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "dashboard_id": {
                        "type": "string",
                        "description": "UUID of the dashboard to retrieve.",
                    },
                },
                "required": ["dashboard_id"],
                "additionalProperties": False,
            },
        },
    },
]


def _chart_to_dict(chart: Chart) -> dict[str, Any]:
    return chart.model_dump(mode="json")


def _dashboard_to_dict(dashboard: Dashboard) -> dict[str, Any]:
    return dashboard.model_dump(mode="json")


def _format_timestamp(timestamp_ms: int) -> str:
    return datetime.datetime.fromtimestamp(timestamp_ms / 1000, tz=datetime.timezone.utc).isoformat()


def _match_score(name: str, query: str) -> tuple[int, int, str]:
    lowered_name = name.lower()
    lowered_query = query.lower()
    exact = 0 if lowered_name == lowered_query else 1
    starts = 0 if lowered_name.startswith(lowered_query) else 1
    return (exact, starts, lowered_name)


def _parse_arguments(arguments: Any) -> dict[str, Any]:
    if arguments is None:
        return {}
    if isinstance(arguments, dict):
        return arguments
    if isinstance(arguments, str):
        trimmed = arguments.strip()
        if not trimmed:
            return {}
        try:
            decoded = json.loads(trimmed)
        except json.JSONDecodeError as exc:
            raise fastapi.HTTPException(status_code=422, detail=f"Tool arguments were invalid JSON: {exc.msg}")
        if not isinstance(decoded, dict):
            raise fastapi.HTTPException(status_code=422, detail="Tool arguments must decode to a JSON object")
        return decoded
    raise fastapi.HTTPException(status_code=422, detail="Tool arguments must be an object or JSON object string")


def execute_ai_tool(
    *,
    user_id: str,
    tool_name: str,
    arguments: Any,
    data_dao: DataDao,
    chart_repo: ChartRepo,
    dashboard_repo: DashboardRepo,
) -> dict[str, Any]:
    parsed_arguments = _parse_arguments(arguments)

    if tool_name == "explain_pulselang":
        _NoArgs.model_validate(parsed_arguments)
        return {
            "name": "PulseLang",
            "summary": (
                "PulseLang is Impulses' small declarative language for defining derived time-series "
                "streams from raw metrics. It uses an S-expression syntax and lets users compose data "
                "fetching, filtering, mapping, rolling windows, bucketization, and aggregation without "
                "changing server code."
            ),
            "core_ideas": [
                "Programs are S-expressions built from literals, symbols, and function calls.",
                "define binds names in the current scope, and lambda creates reusable functions.",
                "data loads a metric stream, and other built-ins transform or combine streams.",
                "Common operations include window, prefix, bucketize, filter, map, and compose.",
                "Built-in aggregates include count, sum, avg, min, max, std, percentiles, and aggregate-from.",
            ],
            "typical_use_cases": [
                "rolling sums or counts over a recent window",
                "derived business metrics such as runway, rates, and ratios",
                "filtering by dimensions or predicates",
                "turning raw event streams into dashboard-friendly series",
            ],
            "runtime_notes": [
                "PulseLang is evaluated through the TypeScript SDK runtime.",
                "The practical compute entry point is compute(client, library, program).",
                "COMMON_LIBRARY provides helper definitions such as duration aliases and common aggregates.",
            ],
            "style_hint": (
                "When explaining a saved chart or dashboard, treat the PulseLang program as the chart's "
                "definition language: explain what data it loads, what transformations it applies, and "
                "what final series it produces."
            ),
        }

    if tool_name == "explain_chart_structure":
        _NoArgs.model_validate(parsed_arguments)
        return {
            "name": "Chart structure",
            "summary": (
                "An Impulses chart is a saved definition of how to compute and render one visualization."
            ),
            "fields": [
                "id: stable UUID of the saved chart",
                "name: human-readable chart name",
                "description: optional free-text explanation",
                "program: PulseLang program that defines the chart's computed data",
                "variables: per-series display configuration such as variable name, alias, color, display type, resolution, roll-up, and right-axis usage",
                "format_y_as_duration_ms: whether Y values should be rendered as durations",
                "interpolate_to_latest: whether line series should be extended to the latest timestamp",
                "cut_future_datapoints: whether datapoints after now should be hidden",
                "default_zoom_window: optional default time window for viewing the chart",
                "created_at and updated_at: timestamps for persistence metadata",
            ],
            "how_to_explain_it": (
                "When describing a chart, explain the name, what the PulseLang program computes, how the variables are presented, and any rendering or zoom defaults that affect how the user sees the result."
            ),
        }

    if tool_name == "display_chart":
        chart_args = DisplayChartArgs.model_validate(parsed_arguments)
        
        if chart_args.chart_id:
            saved_chart = chart_repo.get_chart_by_id(user_id, chart_args.chart_id)
            if not saved_chart:
                raise fastapi.HTTPException(status_code=404, detail="Chart not found")
            full_chart = _chart_to_dict(saved_chart)
            full_chart["chart_derived_from"] = chart_args.chart_derived_from or saved_chart.id
        else:
            full_chart = chart_args.model_dump(exclude_none=True, by_alias=True)

        return {
            "displayed": True,
            "chart_name": full_chart.get("name") or "Chart",
            "full_chart": full_chart,
        }

    if tool_name == "explain_dashboard_structure":
        _NoArgs.model_validate(parsed_arguments)
        return {
            "name": "Dashboard structure",
            "summary": (
                "An Impulses dashboard is a saved layout that groups charts together into one view."
            ),
            "fields": [
                "id: stable UUID of the saved dashboard",
                "name: human-readable dashboard name",
                "description: optional free-text explanation",
                "program: optional dashboard-level PulseLang program shared across the dashboard view",
                "default_zoom_window: optional default time window for the dashboard",
                "override_chart_zoom: whether dashboard zoom settings should override individual chart zoom behavior",
                "layout: array describing which charts are included and how they are positioned or sized",
                "each layout item typically references a chartId and view/layout attributes such as width, height, or other per-placement settings",
                "created_at and updated_at: timestamps for persistence metadata",
            ],
            "how_to_explain_it": (
                "When describing a dashboard, explain which charts it contains, whether it has dashboard-level computation or zoom behavior, and how the layout organizes the charts into one combined view."
            ),
        }

    if tool_name == "list_metric_names":
        _NoArgs.model_validate(parsed_arguments)
        metric_names = sorted(data_dao.list_metric_names(user_id))
        return {
            "metric_names": metric_names,
        }

    if tool_name == "get_metric_last_10_datapoints":
        args = _MetricNameArgs.model_validate(parsed_arguments)
        datapoints = data_dao.get_metric_by_metric_name(user_id, args.metric_name).root
        return {
            "metric_name": args.metric_name,
            "datapoints": [
                {
                    "timestamp": dp.timestamp,
                    "timestamp_human": _format_timestamp(dp.timestamp),
                    "dimensions": dict(dp.dimensions),
                    "value": dp.value,
                }
                for dp in datapoints[-10:]
            ],
        }

    if tool_name == "get_metric_summary":
        args = _MetricNameArgs.model_validate(parsed_arguments)
        datapoints = data_dao.get_metric_by_metric_name(user_id, args.metric_name).root

        if not datapoints:
            return {
                "metric_name": args.metric_name,
                "number_of_points": 0,
                "unique_dimension_keys": [],
                "time_range": {
                    "first_timestamp": None,
                    "first_timestamp_human": None,
                    "last_timestamp": None,
                    "last_timestamp_human": None,
                },
                "min_value": None,
                "max_value": None,
                "unique_dimensions_count": 0,
            }

        first_timestamp = datapoints[0].timestamp
        last_timestamp = datapoints[-1].timestamp
        unique_dimension_keys = sorted({
            key
            for dp in datapoints
            for key in dp.dimensions.keys()
        })
        unique_dimensions_count = len({
            tuple(sorted(dp.dimensions.items()))
            for dp in datapoints
        })
        values = [dp.value for dp in datapoints]

        return {
            "metric_name": args.metric_name,
            "number_of_points": len(datapoints),
            "unique_dimension_keys": unique_dimension_keys,
            "time_range": {
                "first_timestamp": first_timestamp,
                "first_timestamp_human": _format_timestamp(first_timestamp),
                "last_timestamp": last_timestamp,
                "last_timestamp_human": _format_timestamp(last_timestamp),
            },
            "min_value": min(values),
            "max_value": max(values),
            "unique_dimensions_count": unique_dimensions_count,
        }

    if tool_name == "get_metric_common_dimensions":
        args = _MetricNameArgs.model_validate(parsed_arguments)
        datapoints = data_dao.get_metric_by_metric_name(user_id, args.metric_name).root

        dimension_counts: dict[tuple[tuple[str, str], ...], int] = {}
        for dp in datapoints:
            key = tuple(sorted(dp.dimensions.items()))
            dimension_counts[key] = dimension_counts.get(key, 0) + 1

        top_dimension_maps = sorted(
            (
                {
                    "dimensions": dict(key),
                    "count": count,
                }
                for key, count in dimension_counts.items()
            ),
            key=lambda item: (-item["count"], json.dumps(item["dimensions"], sort_keys=True)),
        )[:10]

        return {
            "metric_name": args.metric_name,
            "number_of_points": len(datapoints),
            "unique_dimensions_count": len(dimension_counts),
            "top_dimension_maps": top_dimension_maps,
        }

    if tool_name == "list_charts":
        _NoArgs.model_validate(parsed_arguments)
        charts = chart_repo.list_charts(user_id)
        return {
            "charts": [
                {
                    "id": chart.id,
                    "name": chart.name,
                }
                for chart in charts
            ],
        }

    if tool_name == "get_chart":
        args = _ChartIdArgs.model_validate(parsed_arguments)
        chart = chart_repo.get_chart_by_id(user_id, args.chart_id)
        if not chart:
            raise fastapi.HTTPException(status_code=404, detail="Chart not found")
        return {
            "chart": _chart_to_dict(chart),
        }

    if tool_name == "list_dashboards":
        _NoArgs.model_validate(parsed_arguments)
        dashboards = dashboard_repo.list_dashboards(user_id)
        return {
            "dashboards": [
                {
                    "id": dashboard.id,
                    "name": dashboard.name,
                }
                for dashboard in dashboards
            ],
        }

    if tool_name == "get_dashboard":
        args = _DashboardIdArgs.model_validate(parsed_arguments)
        dashboard = dashboard_repo.get_dashboard_by_id(user_id, args.dashboard_id)
        if not dashboard:
            raise fastapi.HTTPException(status_code=404, detail="Dashboard not found")
        return {
            "dashboard": _dashboard_to_dict(dashboard),
        }

    raise fastapi.HTTPException(status_code=422, detail=f"Unknown tool: {tool_name}")
