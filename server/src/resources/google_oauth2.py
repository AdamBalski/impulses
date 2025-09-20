import json
import urllib
import logging
import httpx
import fastapi
import typing
import base64
from src import state
from fastapi import responses
from google.oauth2 import credentials

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

def check_for_scopes(scopes: typing.List[str]):
    for scope in SCOPES:
        if scope not in scopes:
            raise fastapi.HttpException(status_code=400, details=f"Not all scopes included. Needed scopes: {SCOPES}")


router = fastapi.APIRouter()
@router.get("/callback")
async def oauth2_callback(request: fastapi.Request, code: str, 
                          state: state.AppState = fastapi.Depends(state.get_state)):
    oauth2_state = state.get_google_oauth2_state()
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            oauth2_state.get_app_creds()["web"]["token_uri"],
            data=prepare_response_body_for_refresh_token_request(
                oauth2_state.get_app_creds(), 
                code,
                state.get_origin())
        )

    try:
        resp.raise_for_status()
        token_data = resp.json()
        if (id_token := token_data["id_token"]) and (refresh_token := token_data.get("refresh_token")):
            # id_token is a JWT, sub is an immutable google acc identifier
            scopes = token_data.get("scopes")
            check_for_scopes(scopes)
            creds = construct_credentials(token_data.get("access_token"),
                                          token_data.get("refresh_token"),
                                          oauth2_state,
                                          scopes=scopes))
            user_id = get_sub(id_token)
            # todo: insecure: stripping should be opt-in instead of opt-out
            stripped_creds = creds.to_json(strip=["access_token", "refresh_token", "token", "client_secret"])
            logging.debug(f"Setting gOAuth2 gCal creds for user: {user_id}. Creds: {stripped_creds}")
            oauth2_state.get_tokens(user_id).set_creds(creds)
            return {"status": "ok"}
    except Exception as e:
        logging.error("Caught an error during oauth2 code for token exchange", e)
        raise
    raise fastapi.HTTPException(status_code=500, detail="Internal Server Error")

@router.get("/auth")
async def redirect_to_google(request: fastapi.Request, state: state.AppState = fastapi.Depends(state.get_state)):
    client_creds = state.get_google_oauth2_state().get_app_creds()
    base_url = "https://accounts.google.com/o/oauth2/auth"
    params = {
        "response_type": "code",
        "client_id": client_creds["web"]["client_id"],
        "redirect_uri": state.get_origin() + "/oauth2/google/callback",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent"
    }

    return responses.RedirectResponse(f"{base_url}?{urllib.parse.urlencode(params)}")

