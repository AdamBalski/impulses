import abc
from typing import Mapping, Tuple, Optional, Callable, Self

class Datapoint:
    def __init__(self, timestamp: int, value: float, dimensions: Optional[Mapping[str, str]] = None):
        self.timestamp = timestamp
        self.value = value
        if dimensions == None:
            dimensions = {}
        self.dimensions = dimensions
    def is_not_after(self, other: 'Datapoint') -> bool:
        return self.timestamp <= other.timestamp
    def to_tuple(self) -> Tuple[int, float]:
        return (self.timestamp, self.value)
    def to_api_obj(self):
        return {
                "timestamp": self.timestamp,
                "value": self.value,
                "dimensions": self.dimensions
        }
    @staticmethod
    def from_api_obj(dto):
        return Datapoint(dto["timestamp"], dto["value"], dto["dimensions"])
    def __str__(self):
        return "Datapoint{" + f"val@{self.timestamp} = {self.value}" + "}"
    def __repr__(self):
        return str(self)

class EvaluatedImpulse(abc.ABC):
    @abc.abstractmethod
    def is_constant(self) -> bool:
        pass
    @abc.abstractmethod
    def get_init_val(self) -> float:
        pass
    def as_dp_series(self) -> "DatapointSeries":
        raise Exception("Not a models.DatapointSeries")

class DatapointSeries(EvaluatedImpulse):
    def __init__(self, series = None, init_val = 0.0):
        if series == None:
            series = []
        self.series = series
        self.init_val = init_val
    def as_dp_series(self) -> Self:
        return self
    def time_at(self, idx: int) -> int:
        return self.series[idx].timestamp
    def value_at(self, idx: int) -> float:
        return self.series[idx].value
    def get_init_val(self) -> float:
        return self.init_val
    def __len__(self) -> int:
        return len(self.series)
    def __getitem__(self, idx: int) -> Datapoint:
        return self.series[idx]
    def is_empty(self) -> bool:
        return len(self) == 0
    def is_constant(self) -> bool:
        return False
    def decompose(self):
        return [dp.timestamp for dp in self.series], [dp.value for dp in self.series]
    def filter(self, predicate: Callable[[Datapoint], bool]) -> EvaluatedImpulse:
        return DatapointSeries([dp for dp in self.series if predicate(dp)], self.init_val)
    def map(self, mapping_func: Callable[[Datapoint], Datapoint]) -> EvaluatedImpulse:
        return DatapointSeries([mapping_func(dp) for dp in self.series], self.init_val)
    def __iter__(self):
        return self.series.__iter__()
    def to_api_obj(self):
        return [dp.to_api_obj() for dp in self.series]
    @staticmethod
    def from_api_obj(series):
        return DatapointSeries(series = [Datapoint.from_api_obj(dp) for dp in series])
    def __str__(self):
        return "DatapointSeries{series=[" + ", ".join([str(dp) for dp in self.series]) + \
                "], init_val=" + str(self.init_val) + "}"
    def __repr__(self):
        return str(self)

class ConstantImpulse(EvaluatedImpulse):
    def __init__(self, value: float):
        self.value = value
    def get_init_val(self) -> float:
        return self.value
    def is_constant(self) -> bool:
        return True
    def filter(self) -> EvaluatedImpulse:
        return self

