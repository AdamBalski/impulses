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
        return "Datapoint{" + f"val@<{self.dimensions}>{self.timestamp} = {self.value}" + "}"
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
    def prefix_op(self, operation: Callable[[list[float]], float]) -> 'DatapointSeries':
        """Apply a prefix operation (cumulative operation) over the series.
        
        Args:
            operation: Function that takes [previous_value, current_value] and returns new value
        
        Returns:
            DatapointSeries with cumulative values
        
        Example:
            >>> series.prefix_op(sum)  # cumulative sum
            >>> series.prefix_op(lambda vals: vals[0] + vals[1] * 2)  # weighted sum
        """
        prev = self.init_val
        res_arr = []
        for dp in self:
            prev = operation([prev, dp.value])
            res_arr.append(Datapoint(dp.timestamp, prev, dp.dimensions))
        return DatapointSeries(res_arr, operation([self.init_val]))
    def sliding_window(self, 
                      window: int, 
                      operation: Callable[[list[float]], float],
                      fluid_phase_out: bool = True) -> 'DatapointSeries':
        """Apply a sliding window operation over the series.
        
        Args:
            window: Length of the window in time units
            operation: Function to apply to values in each window (e.g., sum, statistics.mean)
            fluid_phase_out: If True, continue window after last datapoint until empty (default: True)
        
        Returns:
            DatapointSeries with windowed values
        
        Example:
            >>> series.sliding_window(30, sum)  # 30-day rolling sum
            >>> series.sliding_window(7, statistics.mean)  # 7-day moving average
        """
        import heapq
        import collections
        
        if len(self) == 0:
            return DatapointSeries([], self.init_val)
        
        result_dps = []
        val_cnt = 0
        values = collections.defaultdict(int)
        events = [(dp.timestamp, "add", dp.value) for dp in self]
        heapq.heapify(events)
        
        while events:
            time, kind, val = heapq.heappop(events)
            if not fluid_phase_out and time > self.series[-1].timestamp:
                break
            if kind == "add":
                val_cnt += 1
                values[val] += 1
                heapq.heappush(events, (time + window, "remove", val))
            else:
                val_cnt -= 1
                values[val] -= 1
            
            # Don't push two datapoints with the same timestamp
            if events and events[0][0] == time:
                continue
            
            # No values => use init_val
            if val_cnt == 0:
                result_dps.append(Datapoint(time, self.init_val))
                continue
            
            # Flatten values for operation
            flat = []
            for v, c in values.items():
                flat.extend([v] * c)
            result_dps.append(Datapoint(time, operation(flat)))
        
        if fluid_phase_out and result_dps:
            # Remove the init_val that's been added after removing the last datapoint
            result_dps.pop()
        
        return DatapointSeries(result_dps, self.init_val)
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

