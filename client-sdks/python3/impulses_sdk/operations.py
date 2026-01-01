import heapq
import collections
import typing
from . import models

def compose_impulses(evaled_impulses: typing.List[models.EvaluatedImpulse], operation):
    """Composes impulses, e.g. adding or multiplying them.
    """
    indices = [0 for _ in evaled_impulses]
    last_vals = [evaled_impulse.get_init_val() for evaled_impulse in evaled_impulses]
    new_init = operation([series.get_init_val() for series in evaled_impulses])

    pq = []
    constant = True
    for i, evaled_impulse in enumerate(evaled_impulses):
        if evaled_impulse.is_constant():
            continue
        series = evaled_impulse.as_dp_series()
        constant = False
        pq.append((series.time_at(0), series.value_at(0), i))
    if constant or not pq:
        return models.ConstantImpulse(new_init)
    heapq.heapify(pq)

    result = []

    curr_time = min(dp_with_index[0] for dp_with_index in pq)
    def flush(new_time: int) -> None:
        nonlocal curr_time
        result.append(models.Datapoint(curr_time, operation(last_vals)))
        curr_time = new_time
    def maybe_heappush_from(series_idx: int) -> None:
        indices[series_idx] += 1
        if indices[series_idx] < len(evaled_impulses[series_idx].as_dp_series()):
            datapoint = evaled_impulses[series_idx].as_dp_series()[indices[series_idx]]
            heapq.heappush(pq, (datapoint.timestamp, datapoint.value, series_idx))
        
    # pq is always non-empty at the beginning, thus new_time 
    # is guaranteed to be populated with a proper value
    new_time = -1
    while pq:
        new_time, new_val, series_idx = heapq.heappop(pq)
        maybe_heappush_from(series_idx)
        if new_time > curr_time:
            flush(new_time)
        last_vals[series_idx] = new_val
    flush(new_time)

    return models.DatapointSeries(series=result, init_val=new_init)