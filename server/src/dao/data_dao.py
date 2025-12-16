import pydantic
import logging
import typing
from src.db import dao

class PerTimestampDimensionsKey:
    def __init__(self, dimensions, timestamp):
        self.timestamp = timestamp
        self.dimensions = dimensions
        entries = frozenset(dimensions.items())
        self.hash = hash((self.timestamp, entries))
    def __hash__(self):
        return self.hash
    def __eq__(self, other):
        return self.dimensions == other.dimensions \
            and self.timestamp == other.timestamp
class DatapointDto(pydantic.BaseModel):
    timestamp: int
    dimensions: typing.Mapping[str, str]
    value: float
class DatapointsDto(pydantic.RootModel):
    root: typing.List[DatapointDto]
class StringsListDto(pydantic.RootModel):
    root: typing.List[str]

MetricType = dao.Type.for_pydantic_model(DatapointsDto, lambda: DatapointsDto([]))
StringsListType = dao.Type.for_pydantic_model(StringsListDto, lambda: StringsListDto([]))

class DataDao:
    def __init__(self, dao_instance: dao.PersistentDao):
        self.metric_dao = dao.TypedPersistentDao(dao_instance, MetricType)
        self.metric_names_dao = dao.TypedPersistentDao(dao_instance, StringsListType)
    def _metric_names_path(self, user_id: str) -> list[str]:
        return ["users", user_id, "metric_names"]
    def _metric_path(self, user_id: str, metric_name: str) -> list[str]:
        return ["users", user_id, "data", metric_name]
    def add(self, user_id: str, metric_name: str, dps: typing.List[DatapointDto]):
        self.log_duplicates(dps)

        with self.metric_names_dao.locked_access(self._metric_names_path(user_id)) as (__metric_names, set_metric_names):
            metric_names = __metric_names.root
            if metric_name not in metric_names:
                metric_names = metric_names + [metric_name]
                set_metric_names(StringsListDto(metric_names))

        with self.metric_dao.locked_access(self._metric_path(user_id, metric_name)) as (datapoints, set_datapoints):
            dp_list = datapoints.root

            datapoints_map = {PerTimestampDimensionsKey(dp.dimensions, dp.timestamp): dp.value for dp in dp_list}
            for dp in dps:
                datapoints_map[PerTimestampDimensionsKey(dp.dimensions, dp.timestamp)] = dp.value
            dp_list = [DatapointDto(timestamp=k.timestamp, dimensions=k.dimensions, value=v)
                    for k, v in datapoints_map.items()]
            dp_list.sort(key=lambda dp: dp.timestamp)
            set_datapoints(DatapointsDto(dp_list))

    def list_metric_names(self, user_id: str) -> list[str]:
        return self.metric_names_dao.read(self._metric_names_path(user_id)).root
    def get_metric_by_metric_name(self, user_id: str, metric_name: str):
        return self.metric_dao.read(self._metric_path(user_id, metric_name))
    def delete_metric_name(self, user_id: str, metric_name: str):
        with self.metric_names_dao.locked_access(self._metric_names_path(user_id)) as (__metric_names, set_metric_names):
            metric_names = __metric_names.root
            set_metric_names(StringsListDto([name for name in metric_names if name != metric_name]))
        return self.metric_dao.delete(self._metric_path(user_id, metric_name))
    def log_duplicates(self, dps: list[DatapointDto]):
        dps_map = {}
        for dp in dps:
            key = PerTimestampDimensionsKey(dp.dimensions, dp.timestamp)
            if key in dps_map:
                logging.warning(f"Duplicate data points inserted: {dps_map[key]}, {dp}")
            dps_map[key] = dp.value

