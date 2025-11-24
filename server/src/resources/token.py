import secrets
import time

import fastapi
import pydantic

from src.auth import user_auth
from src.auth.token_cache import TokenCache
from src.common import state
from src.dao.gcal_dao import GCalDao
from src.dao.token_repo import TokenRepo, Token as TokenModel

router = fastapi.APIRouter()

class CreateTokenBody(pydantic.BaseModel):
    name: str
    capability: str
    expires_at: int | None = None

class TokenDto(pydantic.BaseModel):
    id: str
    name: str
    capability: str
    expires_at: int
    created_at: int | None = None

class TokenCreatedDto(TokenDto):
    """Response for token creation - includes plaintext token (returned only once)."""
    token_plaintext: str

def _to_token_dto(t: TokenModel) -> TokenDto:
    return TokenDto(id=t.id, name=t.name, capability=t.capability, expires_at=t.expires_at, created_at=t.created_at)

@router.get("")
async def list_tokens(tokens: TokenRepo = state.injected(TokenRepo),
                      u = fastapi.Depends(user_auth.get_current_user)) -> list[TokenDto]:
    res = tokens.list_tokens(u.id)
    return [_to_token_dto(t) for t in res]

@router.post("")
async def create_token(body: CreateTokenBody,
                       tokens: TokenRepo = state.injected(TokenRepo),
                       u = fastapi.Depends(user_auth.get_current_user)) -> TokenCreatedDto:
    if body.capability not in ("API", "INGEST", "SUPER"):
        raise fastapi.HTTPException(status_code=422, detail="Invalid capability")
    # Max liveness 1 year
    now = int(time.time())
    max_exp = now + 365 * 24 * 3600
    exp = body.expires_at if body.expires_at is not None else max_exp
    if exp > max_exp:
        exp = max_exp
    token_plain = secrets.token_urlsafe(48)
    token_hash = TokenCache.hash_token_for_storage(token_plain)
    created = tokens.create_token(u.id, body.name, body.capability, exp, token_hash)
    
    # Add to cache
    cache: TokenCache = state.get_state().get_obj(TokenCache)
    cache.add(token_plain, u.id, body.capability, exp)
    
    # Return token with plaintext (only returned once on creation)
    return TokenCreatedDto(
        id=created.id,
        name=created.name,
        capability=created.capability,
        expires_at=created.expires_at,
        created_at=created.created_at,
        token_plaintext=token_plain
    )

@router.delete("/{token_id}")
async def delete_token(token_id: str,
                       tokens: TokenRepo = state.injected(TokenRepo),
                       cache: TokenCache = state.injected(TokenCache),
                       gcal_dao: GCalDao = state.injected(GCalDao),
                       u = fastapi.Depends(user_auth.get_current_user)) -> None:
    # Get token by id and validate ownership
    token = tokens.get_token_by_id(token_id)
    if not token or token.user_id != u.id:
        raise fastapi.HTTPException(status_code=404, detail="Token not found")

    # Delete GCal credentials from file storage (namespaced by token id)
    gcal_dao.delete_credentials(token.id)

    # Remove from in-memory cache using token hash (if present)
    if token.token_hash:
        cache.remove_by_hash(token.token_hash)

    # Delete token from database by id scoped to user
    tokens.delete_token_by_id(u.id, token.id)

    return None
