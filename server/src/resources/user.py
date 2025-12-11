import bcrypt
import fastapi
import pydantic
import psycopg

from src.auth import user_auth
from src.auth.session import SessionStore
from src.auth.token_cache import TokenCache
from src.common import state
from src.dao.user_repo import UserRepo, User as UserModel

router = fastapi.APIRouter()

class CreateUserBody(pydantic.BaseModel):
    email: str
    password: str
    role: str  # ADMIN | STANDARD

class LoginBody(pydantic.BaseModel):
    email: str
    password: str

class UserDto(pydantic.BaseModel):
    id: str
    email: str
    role: str
    created_at: str | None = None

class LoginResponse(pydantic.BaseModel):
    user: UserDto

def _secure_cookie_flag(origin: str) -> bool:
    return origin.startswith("https://")

def _to_user_dto(u: UserModel) -> UserDto:
    return UserDto(id=u.id, email=u.email, role=u.role, created_at=u.created_at)

@router.post("")
async def create_user(body: CreateUserBody,
                      users: UserRepo = state.injected(UserRepo),
                      app_state: state.AppState = fastapi.Depends(state.get_state)) -> UserDto:
    role = body.role.upper()
    if role not in ("ADMIN", "STANDARD"):
        raise fastapi.HTTPException(status_code=422, detail="role must be ADMIN or STANDARD")
    password_hash = bcrypt.hashpw(body.password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    try:
        created = users.create_user(body.email, password_hash, role)
        return _to_user_dto(created)
    except psycopg.errors.UniqueViolation:
        raise fastapi.HTTPException(status_code=409, detail="User with this email already exists")

@router.post("/login")
async def login(body: LoginBody,
                users: UserRepo = state.injected(UserRepo),
                sessions: SessionStore = state.injected(SessionStore),
                app_state: state.AppState = fastapi.Depends(state.get_state),
                response: fastapi.Response = None) -> LoginResponse:
    u = users.get_user_by_email(body.email)
    if u is None or u.password_hash is None:
        raise fastapi.HTTPException(status_code=401, detail="Invalid credentials")
    if not bcrypt.checkpw(body.password.encode("utf-8"), u.password_hash.encode("utf-8")):
        raise fastapi.HTTPException(status_code=401, detail="Invalid credentials")
    token, sess = sessions.create(u.id, u.email, u.role)
    secure = _secure_cookie_flag(app_state.get_origin())
    response.set_cookie(
        key="sid",
        value=token,
        httponly=True,
        samesite="lax",
        secure=secure,
        path="/",
    )
    return LoginResponse(user=_to_user_dto(u))

@router.post("/logout")
async def logout(response: fastapi.Response,
                 sessions: SessionStore = state.injected(SessionStore),
                 app_state: state.AppState = fastapi.Depends(state.get_state),
                 sid_and_sess = fastapi.Depends(user_auth.get_session_and_token)) -> dict:
    sid, sess = sid_and_sess
    sessions.revoke(sid)
    secure = _secure_cookie_flag(app_state.get_origin())
    # Clear cookie
    response.delete_cookie(key="sid", httponly=True, samesite="lax", secure=secure, path="/")
    return {"status": "logged_out"}

@router.post("/refresh")
async def refresh(response: fastapi.Response,
                  sessions: SessionStore = state.injected(SessionStore),
                  users: UserRepo = state.injected(UserRepo),
                  app_state: state.AppState = fastapi.Depends(state.get_state),
                  sid_and_sess = fastapi.Depends(user_auth.get_session_and_token)) -> LoginResponse:
    sid, sess = sid_and_sess
    new_sid, sess2 = sessions.rotate(sid)
    if not sess2:
        raise fastapi.HTTPException(status_code=401, detail="Invalid session")
    secure = _secure_cookie_flag(app_state.get_origin())
    response.set_cookie(key="sid", value=new_sid, httponly=True, samesite="lax", secure=secure, path="/")
    u = users.get_user_by_id(sess2.user_id)
    if not u:
        raise fastapi.HTTPException(status_code=404, detail="User not found")
    return LoginResponse(user=_to_user_dto(u))

@router.get("")
async def get_current(u: UserModel = fastapi.Depends(user_auth.get_current_user)) -> UserDto:
    return _to_user_dto(u)

@router.delete("")
async def delete_current(sessions: SessionStore = state.injected(SessionStore),
                         cache: TokenCache = state.injected(TokenCache),
                         u: UserModel = fastapi.Depends(user_auth.get_current_user),
                         users: UserRepo = state.injected(UserRepo)) -> None:
    users.soft_delete_user(u.id)
    sessions.revoke_user(u.id)
    cache.invalidate_user_tokens(u.id)
    return None
