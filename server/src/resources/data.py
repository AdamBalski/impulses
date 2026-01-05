import fastapi
import pydantic
import re
import string
import typing
from src.dao import data_dao
from src.common import state
from src.auth import token_auth

VALID_SYMBOL_CHARACTERS = string.ascii_letters + string.digits + "!$%&*+,-.:;<=>?@_()[]{}"
def raise_invalid_symbol_exception(symbol_type: str, symbol: str):
    raise fastapi.HTTPException(status_code=422, detail=f"{symbol_type} ({symbol}) is invalid. "\
            "E.g. incorrect length (should be more than 0 characters and less than 100 "\
            "or contains characters outside of the alphabet ('{VALID_SYMBOL_CHARACTERS}'))")
def is_symbol_valid(symbol: str) -> bool:
    if not (0 < len(symbol) < 100):
        return False
    return all(c in VALID_SYMBOL_CHARACTERS for c in symbol)
def assert_metric_name_validity(metric_name):
    if not is_symbol_valid(metric_name):
        raise_invalid_symbol_exception("Metric name", metric_name)
def assert_dp_validity(dp: data_dao.DatapointDto):
    for dim_key in dp.dimensions:
        if not is_symbol_valid(dim_key):
            raise_invalid_symbol_exception("Dimension key", dim_key)
def assert_metric_name_is_writable(metric_name: str):
    if metric_name.startswith("imp."):
        raise fastapi.HTTPException(status_code=403, 
                                    detail=f"Can't write to a metric name that starts with 'imp.'")
def assert_dps_validity(dps: typing.List[data_dao.DatapointDto]):
    for dp in dps:
        assert_dp_validity(dp)

router = fastapi.APIRouter()


class ComputeRequest(pydantic.BaseModel):
    expression: str


class ComputeJsonRequest(pydantic.BaseModel):
    ast: dict

def _tokenize_sexpr(src: str) -> list[str]:
    tokens: list[str] = []
    i = 0
    n = len(src)
    while i < n:
        c = src[i]
        if c.isspace():
            i += 1
            continue
        if c in '()':
            tokens.append(c)
            i += 1
            continue
        if c == '"':
            j = i + 1
            out = []
            while j < n:
                ch = src[j]
                if ch == '\\':
                    if j + 1 >= n:
                        raise fastapi.HTTPException(status_code=422, detail="Invalid string escape in expression")
                    out.append(src[j + 1])
                    j += 2
                    continue
                if ch == '"':
                    tokens.append('"' + ''.join(out) + '"')
                    j += 1
                    break
                out.append(ch)
                j += 1
            else:
                raise fastapi.HTTPException(status_code=422, detail="Unterminated string literal in expression")
            i = j
            continue

        j = i
        while j < n and (not src[j].isspace()) and src[j] not in '()':
            j += 1
        tokens.append(src[i:j])
        i = j
    return tokens


def _parse_atom(tok: str):
    if tok.startswith('"') and tok.endswith('"') and len(tok) >= 2:
        return tok[1:-1]
    if re.fullmatch(r"-?\d+", tok):
        return int(tok)
    if re.fullmatch(r"-?(\d+\.\d*|\d*\.\d+)", tok):
        return float(tok)
    return tok


def _parse_sexpr(tokens: list[str]):
    idx = 0

    def parse_one():
        nonlocal idx
        if idx >= len(tokens):
            raise fastapi.HTTPException(status_code=422, detail="Unexpected end of expression")
        tok = tokens[idx]
        if tok == '(':
            idx += 1
            arr = []
            while True:
                if idx >= len(tokens):
                    raise fastapi.HTTPException(status_code=422, detail="Unclosed '(' in expression")
                if tokens[idx] == ')':
                    idx += 1
                    return arr
                arr.append(parse_one())
        if tok == ')':
            raise fastapi.HTTPException(status_code=422, detail="Unexpected ')' in expression")
        idx += 1
        return _parse_atom(tok)

    expr = parse_one()
    if idx != len(tokens):
        raise fastapi.HTTPException(status_code=422, detail="Trailing tokens in expression")
    return expr


class _Evaluated(typing.Protocol):
    def is_constant(self) -> bool: ...
    def init_val(self) -> float: ...
    def series(self) -> list[data_dao.DatapointDto]: ...


class _Const:
    def __init__(self, value: float):
        self.value = float(value)
    def is_constant(self) -> bool:
        return True
    def init_val(self) -> float:
        return self.value
    def series(self) -> list[data_dao.DatapointDto]:
        return []


class _Series:
    def __init__(self, series: list[data_dao.DatapointDto], init_val: float = 0.0):
        self._series = series
        self._init_val = float(init_val)
    def is_constant(self) -> bool:
        return False
    def init_val(self) -> float:
        return self._init_val
    def series(self) -> list[data_dao.DatapointDto]:
        return self._series


def _compose(evaled: list[_Evaluated], op: typing.Callable[[list[float]], float]) -> _Evaluated:
    indices = [0 for _ in evaled]
    last_vals = [e.init_val() for e in evaled]
    new_init = op([e.init_val() for e in evaled])

    pq: list[tuple[int, float, int]] = []
    constant = True
    for i, e in enumerate(evaled):
        if e.is_constant():
            continue
        s = e.series()
        if not s:
            continue
        constant = False
        pq.append((s[0].timestamp, s[0].value, i))

    if constant or not pq:
        return _Const(new_init)

    import heapq
    heapq.heapify(pq)

    result: list[data_dao.DatapointDto] = []
    curr_time = min(t for (t, _, _) in pq)

    def flush(new_time: int) -> None:
        nonlocal curr_time
        result.append(data_dao.DatapointDto(timestamp=curr_time, value=op(last_vals), dimensions={}))
        curr_time = new_time

    def maybe_heappush_from(series_idx: int) -> None:
        indices[series_idx] += 1
        s = evaled[series_idx].series()
        if indices[series_idx] < len(s):
            dp = s[indices[series_idx]]
            heapq.heappush(pq, (dp.timestamp, dp.value, series_idx))

    new_time = -1
    while pq:
        new_time, new_val, series_idx = heapq.heappop(pq)
        maybe_heappush_from(series_idx)
        if new_time > curr_time:
            flush(new_time)
        last_vals[series_idx] = new_val
    flush(new_time)

    return _Series(result, init_val=new_init)


def _prefix_sum(e: _Evaluated) -> _Evaluated:
    if e.is_constant():
        return e
    prev = e.init_val()
    out: list[data_dao.DatapointDto] = []
    for dp in e.series():
        prev = prev + dp.value
        out.append(data_dao.DatapointDto(timestamp=dp.timestamp, value=prev, dimensions=dp.dimensions))
    return _Series(out, init_val=e.init_val())


def _map_linear(e: _Evaluated, mul: float, add: float) -> _Evaluated:
    if e.is_constant():
        return _Const(e.init_val() * float(mul) + float(add))
    out: list[data_dao.DatapointDto] = []
    for dp in e.series():
        out.append(data_dao.DatapointDto(timestamp=dp.timestamp, value=dp.value * float(mul) + float(add), dimensions=dp.dimensions))
    return _Series(out, init_val=e.init_val())


def _where_dim_eq(e: _Evaluated, key: str, expected: str) -> _Evaluated:
    if e.is_constant():
        return e
    out = [dp for dp in e.series() if str(dp.dimensions.get(key)) == expected]
    return _Series(out, init_val=e.init_val())


def _unary_pointwise(e: _Evaluated, fn: typing.Callable[[float], float]) -> _Evaluated:
    if e.is_constant():
        return _Const(fn(e.init_val()))
    out: list[data_dao.DatapointDto] = []
    for dp in e.series():
        out.append(data_dao.DatapointDto(timestamp=dp.timestamp, value=fn(dp.value), dimensions=dp.dimensions))
    return _Series(out, init_val=e.init_val())


def _sliding_window(e: _Evaluated, window: int, op_name: str) -> _Evaluated:
    if e.is_constant():
        return e
    s = e.series()
    if not s:
        return _Series([], init_val=e.init_val())

    def op(vals: list[float]) -> float:
        if not vals:
            return e.init_val()
        if op_name == 'sum':
            return float(sum(vals))
        if op_name == 'mean':
            return float(sum(vals) / len(vals))
        if op_name == 'max':
            return float(max(vals))
        if op_name == 'min':
            return float(min(vals))
        raise fastapi.HTTPException(status_code=422, detail=f"Unknown window operation: {op_name}")

    import collections
    import heapq

    result_dps: list[data_dao.DatapointDto] = []
    val_cnt = 0
    values = collections.defaultdict(int)
    events: list[tuple[int, str, float]] = [(dp.timestamp, 'add', dp.value) for dp in s]
    heapq.heapify(events)

    while events:
        t, kind, val = heapq.heappop(events)
        if kind == 'add':
            val_cnt += 1
            values[val] += 1
            heapq.heappush(events, (t + window, 'remove', val))
        else:
            val_cnt -= 1
            values[val] -= 1

        if events and events[0][0] == t:
            continue

        if val_cnt == 0:
            result_dps.append(data_dao.DatapointDto(timestamp=t, value=e.init_val(), dimensions={}))
            continue

        flat: list[float] = []
        for v, c in values.items():
            if c > 0:
                flat.extend([v] * c)
        result_dps.append(data_dao.DatapointDto(timestamp=t, value=op(flat), dimensions={}))

    if result_dps:
        result_dps.pop()
    return _Series(result_dps, init_val=e.init_val())


def _eval(expr, dao: data_dao.DataDao, user_id: str) -> _Evaluated:
    if isinstance(expr, (int, float)):
        return _Const(float(expr))
    if isinstance(expr, str):
        raise fastapi.HTTPException(status_code=422, detail=f"Unexpected symbol: {expr}")
    if not isinstance(expr, list) or not expr:
        raise fastapi.HTTPException(status_code=422, detail="Invalid expression")

    head = expr[0]
    if head == 'metric':
        if len(expr) != 2 or not isinstance(expr[1], str):
            raise fastapi.HTTPException(status_code=422, detail="metric expects one string argument")
        metric_name = expr[1]
        assert_metric_name_validity(metric_name)
        series = dao.get_metric_by_metric_name(user_id, metric_name).root
        return _Series(series, init_val=0.0)

    if head == 'const':
        if len(expr) != 2 or not isinstance(expr[1], (int, float)):
            raise fastapi.HTTPException(status_code=422, detail="const expects one numeric argument")
        return _Const(float(expr[1]))

    if head in ('add', 'sub', 'mul', 'div'):
        if len(expr) < 3:
            raise fastapi.HTTPException(status_code=422, detail=f"{head} expects at least two arguments")
        args = [_eval(e, dao, user_id) for e in expr[1:]]

        if head == 'add':
            return _compose(args, lambda vals: float(sum(vals)))
        if head == 'mul':
            def mul(vals: list[float]) -> float:
                out = 1.0
                for v in vals:
                    out *= v
                return float(out)
            return _compose(args, mul)
        if head == 'sub':
            def sub(vals: list[float]) -> float:
                if not vals:
                    return 0.0
                out = vals[0]
                for v in vals[1:]:
                    out -= v
                return float(out)
            return _compose(args, sub)
        if head == 'div':
            def div(vals: list[float]) -> float:
                if not vals:
                    return 0.0
                out = vals[0]
                for v in vals[1:]:
                    if v == 0:
                        out = 0.0
                    else:
                        out /= v
                return float(out)
            return _compose(args, div)

    if head in ('neg', 'abs'):
        if len(expr) != 2:
            raise fastapi.HTTPException(status_code=422, detail=f"{head} expects one argument")
        arg = _eval(expr[1], dao, user_id)
        if head == 'neg':
            return _unary_pointwise(arg, lambda v: -v)
        return _unary_pointwise(arg, lambda v: abs(v))

    if head == 'map':
        if len(expr) != 4 or not isinstance(expr[1], (int, float)) or not isinstance(expr[2], (int, float)):
            raise fastapi.HTTPException(status_code=422, detail="map expects: (map <mul:number> <add:number> <expr>)")
        return _map_linear(_eval(expr[3], dao, user_id), float(expr[1]), float(expr[2]))

    if head == 'where':
        if len(expr) != 4 or not isinstance(expr[1], str) or not isinstance(expr[2], str):
            raise fastapi.HTTPException(status_code=422, detail="where expects: (where <dim_key> <expected> <expr>)")
        return _where_dim_eq(_eval(expr[3], dao, user_id), expr[1], expr[2])

    if head == 'prefix':
        if len(expr) != 3 or expr[1] != 'sum':
            raise fastapi.HTTPException(status_code=422, detail="prefix currently supports only: (prefix sum <expr>)")
        return _prefix_sum(_eval(expr[2], dao, user_id))

    if head == 'window':
        if len(expr) != 4 or not isinstance(expr[1], int) or not isinstance(expr[2], str):
            raise fastapi.HTTPException(status_code=422, detail="window expects: (window <int> <op> <expr>)")
        window = expr[1]
        op_name = expr[2]
        return _sliding_window(_eval(expr[3], dao, user_id), window, op_name)

    raise fastapi.HTTPException(status_code=422, detail=f"Unknown operator: {head}")


def _eval_json_ast(node: typing.Any, dao: data_dao.DataDao, user_id: str) -> _Evaluated:
    if isinstance(node, (int, float)):
        return _Const(float(node))
    if isinstance(node, str):
        raise fastapi.HTTPException(status_code=422, detail=f"Unexpected string atom in AST: {node}")
    if not isinstance(node, dict):
        raise fastapi.HTTPException(status_code=422, detail="Invalid AST node")

    op = node.get('op')
    if not isinstance(op, str):
        raise fastapi.HTTPException(status_code=422, detail="AST node missing 'op'")

    if op == 'metric':
        name = node.get('name')
        if not isinstance(name, str):
            raise fastapi.HTTPException(status_code=422, detail="metric requires string field 'name'")
        assert_metric_name_validity(name)
        series = dao.get_metric_by_metric_name(user_id, name).root
        return _Series(series, init_val=0.0)

    if op == 'const':
        value = node.get('value')
        if not isinstance(value, (int, float)):
            raise fastapi.HTTPException(status_code=422, detail="const requires numeric field 'value'")
        return _Const(float(value))

    if op in ('add', 'sub', 'mul', 'div'):
        args_node = node.get('args')
        if not isinstance(args_node, list) or len(args_node) < 2:
            raise fastapi.HTTPException(status_code=422, detail=f"{op} requires list field 'args' with at least 2 elements")
        args = [_eval_json_ast(a, dao, user_id) for a in args_node]
        if op == 'add':
            return _compose(args, lambda vals: float(sum(vals)))
        if op == 'mul':
            def mul(vals: list[float]) -> float:
                out = 1.0
                for v in vals:
                    out *= v
                return float(out)
            return _compose(args, mul)
        if op == 'sub':
            def sub(vals: list[float]) -> float:
                out = vals[0]
                for v in vals[1:]:
                    out -= v
                return float(out)
            return _compose(args, sub)
        def div(vals: list[float]) -> float:
            out = vals[0]
            for v in vals[1:]:
                if v == 0:
                    out = 0.0
                else:
                    out /= v
            return float(out)
        return _compose(args, div)

    if op in ('neg', 'abs'):
        arg = node.get('arg')
        if arg is None:
            raise fastapi.HTTPException(status_code=422, detail=f"{op} requires field 'arg'")
        ev = _eval_json_ast(arg, dao, user_id)
        if op == 'neg':
            return _unary_pointwise(ev, lambda v: -v)
        return _unary_pointwise(ev, lambda v: abs(v))

    if op == 'prefix':
        fn = node.get('fn')
        arg = node.get('arg')
        if fn != 'sum' or arg is None:
            raise fastapi.HTTPException(status_code=422, detail="prefix supports only: {op:'prefix', fn:'sum', arg:<expr>}")
        return _prefix_sum(_eval_json_ast(arg, dao, user_id))

    if op == 'window':
        window = node.get('window')
        fn = node.get('fn')
        arg = node.get('arg')
        if not isinstance(window, int) or not isinstance(fn, str) or arg is None:
            raise fastapi.HTTPException(status_code=422, detail="window requires fields: window:int, fn:str, arg:<expr>")
        return _sliding_window(_eval_json_ast(arg, dao, user_id), window, fn)

    if op == 'where':
        key = node.get('key')
        eq = node.get('eq')
        arg = node.get('arg')
        if not isinstance(key, str) or not isinstance(eq, str) or arg is None:
            raise fastapi.HTTPException(status_code=422, detail="where requires fields: key:str, eq:str, arg:<expr>")
        return _where_dim_eq(_eval_json_ast(arg, dao, user_id), key, eq)

    if op == 'map':
        mul = node.get('mul')
        add = node.get('add')
        arg = node.get('arg')
        if not isinstance(mul, (int, float)) or not isinstance(add, (int, float)) or arg is None:
            raise fastapi.HTTPException(status_code=422, detail="map requires fields: mul:number, add:number, arg:<expr>")
        return _map_linear(_eval_json_ast(arg, dao, user_id), float(mul), float(add))

    raise fastapi.HTTPException(status_code=422, detail=f"Unknown AST op: {op}")


@router.post("/compute")
def compute(payload: ComputeRequest,
            dao = state.injected(data_dao.DataDao),
            user_id: str = fastapi.Depends(token_auth.require_api_token)):
    tokens = _tokenize_sexpr(payload.expression)
    expr = _parse_sexpr(tokens)
    res = _eval(expr, dao, user_id)
    return res.series()


@router.post("/compute-json")
def compute_json(payload: ComputeJsonRequest,
                 dao = state.injected(data_dao.DataDao),
                 user_id: str = fastapi.Depends(token_auth.require_api_token)):
    res = _eval_json_ast(payload.ast, dao, user_id)
    return res.series()

@router.get("")
def list_metric_names(dao = state.injected(data_dao.DataDao),
                      user_id: str = fastapi.Depends(token_auth.require_api_token)):
    return dao.list_metric_names(user_id)

@router.get("/{metric_name}")
def get_metric_by_metric_name(metric_name: str, dao = state.injected(data_dao.DataDao),
                              user_id: str = fastapi.Depends(token_auth.require_api_token)):
    assert_metric_name_validity(metric_name)
    return dao.get_metric_by_metric_name(user_id, metric_name)
    
@router.post("/{metric_name}")
def post_datapoints_for_metric_name(metric_name: str, payload: typing.List[data_dao.DatapointDto],
                                    dao = state.injected(data_dao.DataDao),
                                    user_id: str = fastapi.Depends(token_auth.require_ingest_token)):
    assert_metric_name_validity(metric_name)
    assert_metric_name_is_writable(metric_name)
    assert_dps_validity(payload)
    dao.add(user_id, metric_name, payload)

@router.delete("/{metric_name}")
def delete_metric_name(metric_name: str, dao = state.injected(data_dao.DataDao),
                       user_id: str = fastapi.Depends(token_auth.require_ingest_token)):
    assert_metric_name_validity(metric_name)
    assert_metric_name_is_writable(metric_name)
    dao.delete_metric_name(user_id, metric_name)

