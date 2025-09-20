import json
import urllib
import logging
import httpx
import fastapi
import base64
from src import state
from fastapi import responses
from google.oauth2 import credentials

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

    if resp.status_code != 200:
        raise fastapi.HTTPException(status_code=400, detail="The supplied code was probably incorrect. Google returned non 200OK response.")

    token_data = resp.json()
    creds = credentials.Credentials.from_authorized_user_info(token_data)
    if (id_token := token_data["id_token"]):
        # id_token is a JWT, sub is an immutable google acc identifier
        user_id = get_sub(id_token)
        stripped_creds = creds.to_json(strip=["refresh_token", "access_token"])
        logging.debug(f"Setting gOAuth2 gCal credentials for user: {user_id}. Creds: {stripped_creds}")
        oauth2_state.get_tokens(user_id).set_creds(creds)
        return {"status": "ok"}
    raise fastapi.HTTPException(status_code=500, detail="Internal Server Error")

@router.get("/auth")
async def redirect_to_google(request: fastapi.Request, state: state.AppState = fastapi.Depends(state.get_state)):
    client_creds = state.get_google_oauth2_state().get_app_creds()
    scopes = [
        # job for polling google calendar events
        "https://www.googleapis.com/auth/calendar.readonly",
        # association of google account id to the refresh token
        "https://www.googleapis.com/auth/userinfo.email"
    ]

    base_url = "https://accounts.google.com/o/oauth2/auth"
    params = {
        "response_type": "code",
        "client_id": client_creds["web"]["client_id"],
        "redirect_uri": state.get_origin() + "/oauth2/google/callback",
        "scope": " ".join(scopes),
        "access_type": "offline",
        "prompt": "consent"
    }

    return responses.RedirectResponse(f"{base_url}?{urllib.parse.urlencode(params)}")

