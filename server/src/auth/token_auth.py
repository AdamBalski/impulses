import fastapi

from src.auth.token_cache import TokenCache
from src.common import state


def _parse_data_token_header(x_data_token: str) -> str:
    if not x_data_token:
        raise fastapi.HTTPException(status_code=401, detail="Expected data token")
    return x_data_token

async def _check_data_token(required_caps: set[str],
                            x_data_token: str = fastapi.Header(alias="X-Data-Token"),
                            cache: TokenCache = state.injected(TokenCache)) -> str:
    plaintext = _parse_data_token_header(x_data_token)
    
    result = cache.get(plaintext)
    if not result:
        raise fastapi.HTTPException(status_code=401, detail="Invalid or expired data token")
    
    user_id, capability = result
    
    # SUPER capability bypasses specific capability checks
    if capability == "SUPER":
        return user_id
    
    # Check if token has required capability
    if capability not in required_caps:
        raise fastapi.HTTPException(status_code=403, detail="Insufficient token capability")
    
    return user_id

async def require_api_token(x_data_token: str = fastapi.Header(alias="X-Data-Token"),
                           cache: TokenCache = state.injected(TokenCache)) -> str:
    return await _check_data_token({"API"}, x_data_token, cache)

async def require_ingest_token(x_data_token: str = fastapi.Header(alias="X-Data-Token"),
                               cache: TokenCache = state.injected(TokenCache)) -> str:
    return await _check_data_token({"INGEST"}, x_data_token, cache)
