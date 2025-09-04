from src import health
import typing
import collections

class Tokens:
    def __init__(self):
        self.refresh_token: typing.Optional[str] = None
    def set_refresh_token(self, token: typing.Optional[str]):
        self.refresh_token = token
    def get_refresh_token(self) -> typing.Optional[str]:
        return self.refresh_token

class GoogleOAuth2State:
    def __init__(self, app_oauth2_creds):
        self.user_id_to_tokens_map: typing.Mapping[str, Tokens] = collections.defaultdict(Tokens)
        self.app_oauth2_creds = app_oauth2_creds
    def get_app_creds(self):
        return self.app_oauth2_creds
    def get_tokens(self, user_id):
        return self.user_id_to_tokens_map[user_id]

class AppState:
    def __init__(self, 
                 status: health.AppHealth,
                 app_token: str, 
                 google_oauth2_state: GoogleOAuth2State,
                 origin: str):
        self.status = status
        self.app_token = app_token
        self.google_oauth2_state = google_oauth2_state
        self.origin = origin
    def get_status(self) -> health.AppHealth:
        return self.status
    def get_app_token(self) -> str:
        return self.app_token
    def get_google_oauth2_state(self) -> GoogleOAuth2State:
        return self.google_oauth2_state
    def get_origin(self) -> str:
        return self.origin

_app_state: typing.Optional[AppState]

def set_state(state: AppState):
    global _app_state
    _app_state = state
    return _app_state

def get_state() -> AppState:
    if _app_state is None:
        raise Exception("State not yet loaded")
    return _app_state
