import base64
import json
import logging
import secrets
import time
import urllib

import fastapi
import httpx
from fastapi import responses
from google.oauth2 import credentials

from src.auth import token_auth
from src.auth.token_cache import TokenCache
from src.common import state
from src.dao.gcal_dao import GCalDao
from src.dao.token_repo import TokenRepo

SCOPES = [
    # job for polling google calendar events
    "https://www.googleapis.com/auth/calendar.readonly",
    # association of google account id to the refresh token
    "https://www.googleapis.com/auth/userinfo.email"
]

def get_sub(jwt_token: str) -> str:
    payload = jwt_token.split(".")[1]
    # fix base64 padding
    padded = payload + "=" * (-len(payload) % 4)
    data = json.loads(base64.urlsafe_b64decode(padded))
    return data["sub"]

def prepare_response_body_for_refresh_token_request(oauth2_creds, code, origin):
    return {
        "code": code,
        "client_id": oauth2_creds["web"]["client_id"],
        "client_secret": oauth2_creds["web"]["client_secret"],
        "redirect_uri": origin.rstrip("/") + "/oauth2/google/callback",
        "grant_type": "authorization_code",
    }

def construct_credentials(access_token, refresh_token, oauth2_state: state.GoogleOAuth2State, scopes):
    creds = oauth2_state.get_app_creds()
    return credentials.Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri=creds["web"]["token_uri"],
        client_id=creds["web"]["client_id"],
        client_secret=creds["web"]["client_secret"],
        scopes=scopes,
    )

def check_for_scopes(scopes: list[str]):
    for scope in SCOPES:
        if scope not in scopes:
            raise fastapi.HTTPException(status_code=400, detail=f"Not all scopes included. Needed scopes: {SCOPES}")


router = fastapi.APIRouter()


@router.get("/configs")
async def list_oauth2_configs(
    user_id: str = fastapi.Depends(token_auth.require_api_token),
    app_state: state.AppState = fastapi.Depends(state.get_state),
):
    tokens: TokenRepo = app_state.get_obj(TokenRepo)
    gcal_dao: GCalDao = app_state.get_obj(GCalDao)

    res = []
    for token in tokens.list_tokens(user_id):
        creds = gcal_dao.get_credentials(token.id)
        if not creds:
            continue

        sync_state = gcal_dao.get_sync_state(token.id)

        res.append({
            "provider": "google",
            "product": "calendar",
            "token_id": token.id,
            "token_name": token.name,
            "connected": True,
            "updated_at": creds.updated_at,
            "token_expiry": creds.token_expiry,
            "sync": None if sync_state is None else {
                "calendar_id": sync_state.calendar_id,
                "last_sync_at": sync_state.last_sync_at,
                "has_sync_token": sync_state.sync_token is not None,
            },
        })

    return res

@router.get("/callback")
async def oauth2_callback(
    request: fastapi.Request,
    code: str,
    state_param: str = fastapi.Query(alias="state"),
    app_state: state.AppState = fastapi.Depends(state.get_state)
):
    """Handle Google OAuth callback and store credentials linked to token."""
    oauth2_state = app_state.get_google_oauth2_state()
    tokens: TokenRepo = app_state.get_obj(TokenRepo)
    gcal_dao: GCalDao = app_state.get_obj(GCalDao)
    
    # Retrieve pending auth
    if not hasattr(oauth2_state, '_pending_auths'):
        raise fastapi.HTTPException(status_code=400, detail="Invalid OAuth state")
    
    pending = oauth2_state._pending_auths.get(state_param)
    if not pending:
        raise fastapi.HTTPException(status_code=400, detail="Invalid or expired OAuth state")
    
    # Check if state expired
    if pending["expires_at"] < int(time.time()):
        del oauth2_state._pending_auths[state_param]
        raise fastapi.HTTPException(status_code=400, detail="OAuth state expired")
    
    user_id = pending["user_id"]
    token_id = pending["token_id"]
    token_name = pending["token_name"]
    
    # Cleanup pending auth
    del oauth2_state._pending_auths[state_param]
    
    # Verify token still valid
    token = tokens.get_token_by_id(token_id)
    if not token or token.expires_at < int(time.time()):
        raise fastapi.HTTPException(status_code=401, detail="Token expired or deleted")
    
    # Exchange code for tokens
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            oauth2_state.get_app_creds()["web"]["token_uri"],
            data=prepare_response_body_for_refresh_token_request(
                oauth2_state.get_app_creds(),
                code,
                app_state.get_api_origin())
        )

    try:
        resp.raise_for_status()
        token_data = resp.json()
        if (id_token := token_data["id_token"]) and (refresh_token := token_data.get("refresh_token")):
            # Verify scopes
            scopes = token_data.get("scope").split(" ")
            check_for_scopes(scopes)
            
            # Extract token expiry
            access_token = token_data.get("access_token")
            expires_in = token_data.get("expires_in", 3600)
            token_expiry = int(time.time()) + expires_in
            
            # Store credentials in GCalDao linked to token
            gcal_dao.store_credentials(
                token_id=token_id,
                user_id=user_id,
                access_token=access_token,
                refresh_token=refresh_token,
                token_expiry=token_expiry
            )
            
            logging.info(f"Stored GCal credentials for token {token_id} (user {user_id}, token name {token_name})")

            ui_url = app_state.get_ui_origin().rstrip("/") + "/tokens"
            qs = urllib.parse.urlencode({
                "google_oauth2": "authorized",
                "token_id": str(token_id),
                "token_name": token.name,
            })
            return responses.RedirectResponse(f"{ui_url}?{qs}")
    except Exception as e:
        logging.error(f"Error during OAuth2 code exchange: {e}")
        ui_url = app_state.get_ui_origin().rstrip("/") + "/tokens"
        qs = urllib.parse.urlencode({
            "google_oauth2": "error",
            "detail": str(e),
        })
        return responses.RedirectResponse(f"{ui_url}?{qs}")
    
    raise fastapi.HTTPException(status_code=500, detail="Internal Server Error")

@router.get("/auth")
async def redirect_to_google(
    request: fastapi.Request,
    app_state: state.AppState = fastapi.Depends(state.get_state),
    user_id: str = fastapi.Depends(token_auth.require_api_token)
):
    """
    Start Google OAuth flow.
    Requires X-Data-Token header with API or SUPER capability.
    """
    token_header = request.headers.get("X-Data-Token")
    if not token_header:
        raise fastapi.HTTPException(status_code=400, detail="X-Data-Token header required")

    # Lookup token by hash (aligned with token_auth cache keying)
    token_hash = TokenCache.hash_token_for_storage(token_header)
    tokens: TokenRepo = app_state.get_obj(TokenRepo)
    token = tokens.get_token_by_hash(user_id, token_hash)
    if not token:
        raise fastapi.HTTPException(status_code=404, detail="Token not found")
    
    # Store pending authorization with token_id
    oauth2_state = app_state.get_google_oauth2_state()
    state_key = secrets.token_urlsafe(32)
    
    # Use oauth2_state to store pending auth temporarily
    # Store in a dict attribute if not exists
    if not hasattr(oauth2_state, '_pending_auths'):
        oauth2_state._pending_auths = {}
    oauth2_state._pending_auths[state_key] = {
        "user_id": user_id,
        "token_id": token.id,
        "token_name": token.name,
        "expires_at": int(time.time()) + 600  # 10 min expiry
    }
    
    # Build authorization URL
    client_creds = oauth2_state.get_app_creds()
    base_url = "https://accounts.google.com/o/oauth2/auth"
    params = {
        "response_type": "code",
        "client_id": client_creds["web"]["client_id"],
        "redirect_uri": app_state.get_api_origin() + "/oauth2/google/callback",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "state": state_key  # Pass our state
    }

    return {"url": f"{base_url}?{urllib.parse.urlencode(params)}"}

