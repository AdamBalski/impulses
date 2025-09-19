import heapq
import collections
import typing
from . import models

def compose_impulses(evaled_impulses: typing.List[models.EvaluatedImpulse], operation):
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

def prefix_op(impulse: models.DatapointSeries, operation):
    prev = impulse.init_val
    res_arr = []
    for dp in impulse:
        prev = operation([prev, dp.value])
        res_arr.append(models.Datapoint(dp.timestamp, prev))
    return models.DatapointSeries(res_arr, operation([impulse.init_val]))

def sliding_window(impulse: models.EvaluatedImpulse, 
                   window: int, 
                   operation: typing.Callable[[list[float]], float], 
                   fluid_phase_out = True):
    """
    Does a sliding window operation on the impulse
    :param window: length of one window
    :param operation: operation to apply for data in every window
    :return: returns the impulse after the operation
    """
    if impulse.is_constant() or len(impulse.as_dp_series()) == 0:
        return models.ConstantImpulse(operation([impulse.get_init_val()]))
    impulse = impulse.as_dp_series()
    result_dps = []

    val_cnt = 0
    values = collections.defaultdict(int)
    events = [(dp.timestamp, "add", dp.value) for dp in impulse]
    heapq.heapify(events)
    while events:
        time, kind, val = heapq.heappop(events)
        if not fluid_phase_out and time > impulse.series[-1].timestamp:
            break
        if kind == "add":
            val_cnt += 1
            values[val] += 1
            heapq.heappush(events, (time + window, "remove", val))
        else:
            val_cnt -= 1
            values[val] -= 1
        # don't push two dps with the same time
        if events and events[0][0] == time:
            continue
        # no values => init val
        if val_cnt == 0:
            result_dps.append(models.Datapoint(time, impulse.get_init_val()))
            continue
        flat = []
        for v, c in values.items():
            flat.extend([v] * c)
        result_dps.append(models.Datapoint(time, operation(flat)))

    if fluid_phase_out:
        # pop the init_val that's been added after removing the last dp
        result_dps.pop()
    return models.DatapointSeries(result_dps, impulse.get_init_val())

