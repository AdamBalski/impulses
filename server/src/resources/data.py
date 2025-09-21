import fastapi
import string
import typing
from src.dao import DataDao
from src import state

VALID_SYMBOL_CHARACTERS = string.ascii_letters + string.digits + "!$%&()*+,-.:;<=>?@_()[]{}"
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
def assert_dp_validity(dp: DataDao.DatapointDto):
    for dim_key in dp.dimensions:
        if not is_symbol_valid(dim_key):
            raise_invalid_symbol_exception("Dimension key", dim_key)
def assert_metric_name_is_writable(metric_name: str):
    if metric_name.startswith("imp."):
        raise fastapi.HTTPException(status_code=403, 
                                    detail=f"Can't write to a metric name that starts with 'imp.'")
def assert_dps_validity(dps: typing.List[DataDao.DatapointDto]):
    for dp in dps:
        assert_dp_validity(dp)

router = fastapi.APIRouter()

@router.get("")
def list_metric_names(dao = state.injected(DataDao.DataDao)):
    return dao.list_metric_names()

@router.get("/{metric_name}")
def get_metric_by_metric_name(metric_name: str, dao = state.injected(DataDao.DataDao)):
    assert_metric_name_validity(metric_name)
    return dao.get_metric_by_metric_name(metric_name)
    
@router.post("/{metric_name}")
def post_datapoints_for_metric_name(metric_name: str, payload: typing.List[DataDao.DatapointDto],
                                    dao = state.injected(DataDao.DataDao)):
    assert_metric_name_validity(metric_name)
    assert_metric_name_is_writable(metric_name)
    assert_dps_validity(payload)
    dao.add(metric_name, payload)

@router.delete("/{metric_name}")
def delete_metric_name(metric_name: str, dao = state.injected(DataDao.DataDao)):
    assert_metric_name_validity(metric_name)
    assert_metric_name_is_writable(metric_name)
    dao.delete_metric_name(metric_name)

