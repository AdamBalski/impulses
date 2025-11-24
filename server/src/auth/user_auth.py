import fastapi

from src.auth.session import SessionStore, Session
from src.common import state
from src.dao.user_repo import UserRepo, User as UserModel


async def get_session_token(request: fastapi.Request) -> str:
    sid = request.cookies.get("sid")
    if not sid:
        raise fastapi.HTTPException(status_code=401, detail="No session")
    return sid

async def get_session(sid: str = fastapi.Depends(get_session_token),
                      sessions: SessionStore = state.injected(SessionStore)) -> Session:
    sess = sessions.get(sid)
    if not sess:
        raise fastapi.HTTPException(status_code=401, detail="Invalid session")
    return sess

async def get_current_user(users: UserRepo = state.injected(UserRepo),
                           sess: Session = fastapi.Depends(get_session)) -> UserModel:
    u = users.get_user_by_id(sess.user_id)
    if not u:
        raise fastapi.HTTPException(status_code=404, detail="User not found")
    return u

async def get_session_and_token(sid: str = fastapi.Depends(get_session_token),
                                sessions: SessionStore = state.injected(SessionStore)) -> tuple[str, Session]:
    sess = sessions.get(sid)
    if not sess:
        raise fastapi.HTTPException(status_code=401, detail="Invalid session")
    return sid, sess
