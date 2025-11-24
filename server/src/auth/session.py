from __future__ import annotations

import secrets
import time
import typing


class Session:
    def __init__(self, user_id: str, email: str, role: str, expires_at: float):
        self.user_id = user_id
        self.email = email
        self.role = role
        self.expires_at = expires_at

class SessionStore:
    def __init__(self, ttl_seconds: int = 1800):
        self._sessions: dict[str, Session] = {}
        self._ttl = ttl_seconds

    def create(self, user_id: str, email: str, role: str) -> tuple[str, Session]:
        token = secrets.token_urlsafe(48)
        sess = Session(user_id, email, role, time.time() + self._ttl)
        self._sessions[token] = sess
        return token, sess

    def get(self, token: str) -> typing.Optional[Session]:
        sess = self._sessions.get(token)
        if not sess:
            return None
        if sess.expires_at < time.time():
            self._sessions.pop(token, None)
            return None
        return sess

    def rotate(self, token: str) -> tuple[str, typing.Optional[Session]]:
        sess = self.get(token)
        if not sess:
            return token, None
        new_token, new_sess = self.create(sess.user_id, sess.email, sess.role)
        self._sessions.pop(token, None)
        return new_token, new_sess

    def revoke_user(self, user_id: str) -> None:
        to_delete = [t for t, s in self._sessions.items() if s.user_id == user_id]
        for t in to_delete:
            self._sessions.pop(t, None)

    def revoke(self, token: str) -> None:
        self._sessions.pop(token, None)
