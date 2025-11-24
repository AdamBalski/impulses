"""
Google Calendar DAO for managing OAuth credentials and sync state.
Uses file-based storage (dao.py) with per-token isolation.

Storage structure:
  gcal/
    tokens/
      {token_id}/
        credentials
        sync_state
        event_state
"""

import pydantic
import os
import time
from typing import Optional
from src.db.dao import PersistentDao, Type


class GCalCredentials(pydantic.BaseModel):
    """Google OAuth credentials for a specific token."""
    token_id: str
    user_id: str
    access_token: str
    refresh_token: str
    token_expiry: int  # Unix timestamp
    created_at: int
    updated_at: int


class GCalSyncState(pydantic.BaseModel):
    """Calendar sync state for a token."""
    token_id: str
    calendar_id: str
    sync_token: str | None = None
    last_sync_at: int | None = None


class GCalEvent(pydantic.BaseModel):
    """Cached Google Calendar event."""
    event_id: str
    summary: str
    description: str
    start: str
    end: str


class GCalEventState(pydantic.BaseModel):
    """Event state for a gCal & token"""
    token_id: str
    events: dict[str, GCalEvent]  # event_id -> Event
    
    @staticmethod
    def empty(token_id: str) -> "GCalEventState":
        return GCalEventState(token_id=token_id, events={})


class GCalDao:
    """
    Manage Google Calendar OAuth credentials and sync state.
    """
    
    def __init__(self, dao: PersistentDao):
        self.dao = dao
        self.creds_type = Type.for_pydantic_model(GCalCredentials)
        self.sync_state_type = Type.for_pydantic_model(GCalSyncState)
        self.event_state_type = Type.for_pydantic_model(GCalEventState, lambda: None)
    
    def store_credentials(
        self,
        token_id: str,
        user_id: str,
        access_token: str,
        refresh_token: str,
        token_expiry: int
    ) -> GCalCredentials:
        now = int(time.time())
        
        # Try to load existing to preserve created_at
        existing = self.get_credentials(token_id)
        created_at = existing.created_at if existing else now
        
        creds = GCalCredentials(
            token_id=token_id,
            user_id=user_id,
            access_token=access_token,
            refresh_token=refresh_token,
            token_expiry=token_expiry,
            created_at=created_at,
            updated_at=now
        )
        
        self.dao.flush(["gcal", "tokens", token_id, "credentials"], creds, self.creds_type)
        return creds
    
    def get_credentials(self, token_id: str) -> Optional[GCalCredentials]:
        return self.dao.read(
            ["gcal", "tokens", token_id, "credentials"],
            self.creds_type
        )
    
    def delete_credentials(self, token_id: str) -> None:
        self.dao.delete(["gcal", "tokens", token_id, "credentials"])
        self.dao.delete(["gcal", "tokens", token_id, "sync_state"])
        self.dao.delete(["gcal", "tokens", token_id, "event_state"])

    def get_sync_state(self, token_id: str) -> Optional[GCalSyncState]:
        return self.dao.read(
            ["gcal", "tokens", token_id, "sync_state"],
            self.sync_state_type
        )
    
    def update_sync_state(
        self,
        token_id: str,
        calendar_id: str,
        sync_token: str
    ) -> None:
        state = GCalSyncState(
            token_id=token_id,
            calendar_id=calendar_id,
            sync_token=sync_token,
            last_sync_at=int(time.time())
        )
        
        self.dao.flush(["gcal", "tokens", token_id, "sync_state"], state, self.sync_state_type)
    
    def get_event_state(self, token_id: str) -> GCalEventState:
        state = self.dao.read(
            ["gcal", "tokens", token_id, "event_state"],
            self.event_state_type
        )
        return state if state else GCalEventState.empty(token_id)
    
    def save_event_state(self, state: GCalEventState) -> None:
        self.dao.flush(
            ["gcal", "tokens", state.token_id, "event_state"],
            state,
            self.event_state_type
        )
    
    def list_all_token_ids(self) -> list[str]:
        tokens_dir = self.dao.get_path(["gcal", "tokens"])
        if not os.path.exists(tokens_dir):
            return []
        
        # List directories in gcal/tokens/
        token_ids = []
        try:
            for entry in os.listdir(tokens_dir):
                entry_path = os.path.join(tokens_dir, entry)
                if os.path.isdir(entry_path):
                    token_ids.append(entry)
        except OSError:
            return []
        
        return token_ids
    
    def list_all_credentials(self) -> list[GCalCredentials]:
        token_ids = self.list_all_token_ids()
        credentials = []
        
        for token_id in token_ids:
            creds = self.get_credentials(token_id)
            if creds:
                credentials.append(creds)
        
        return credentials
