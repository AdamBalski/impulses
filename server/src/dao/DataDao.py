import pydantic
import typing
from src.db import Dao

class DatapointDto(pydantic.BaseModel):
    timestamp: int
    dimensions: typing.Mapping[str, str]
    value: float
class DatapointsDto(pydantic.RootModel):
    root: typing.List[DatapointDto]
class StringsListDto(pydantic.RootModel):
    root: typing.List[str]

MetricType = Dao.Type.for_pydantic_model(DatapointsDto, lambda: DatapointsDto([]))
StringsListType = Dao.Type.for_pydantic_model(StringsListDto, lambda: StringsListDto([]))

class DataDao:
    def __init__(self, dao: Dao.PersistentDao):
        self.metric_dao = Dao.TypedPersistentDao(dao, MetricType)
        self.metric_names_dao = Dao.TypedPersistentDao(dao, StringsListType)
    def add(self, metric_name: str, dps: typing.List[DatapointDto]):
        metric_names = []
        with self.metric_names_dao.locked_access(f"metric_names") as (__metric_names, set_metric_names):
            metric_names = __metric_names.root
            if metric_name not in metric_names:
                metric_names = metric_names + [metric_name]
                set_metric_names(StringsListDto(metric_names))

        with self.metric_dao.locked_access(f"data#{metric_name}") as (datapoints, set_datapoints):
            dp_list = datapoints.root
            class Key:
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

            datapoints_map = {Key(dp.dimensions, dp.timestamp): dp.value for dp in dp_list}
            for dp in dps:
                datapoints_map[Key(dp.dimensions, dp.timestamp)] = dp.value
            dp_list = [DatapointDto(timestamp=k.timestamp, dimensions=k.dimensions, value=v)
                    for k, v in datapoints_map.items()]
            dp_list.sort(key=lambda dp: dp.timestamp)
            set_datapoints(DatapointsDto(dp_list))

    def list_metric_names(self) -> list[str]:
        return self.metric_names_dao.read("metric_names")
    def get_metric_by_metric_name(self, metric_name: str):
        return self.metric_dao.read(f"data#{metric_name}")
    def delete_metric_name(self, metric_name: str):
        with self.metric_names_dao.locked_access(f"metric_names") as (__metric_names, set_metric_names):
            metric_names = __metric_names.root
            set_metric_names(StringsListDto([name for name in metric_names if name != metric_name]))
        return self.metric_dao.delete(f"data#{metric_name}")

