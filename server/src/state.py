import datetime
import fastapi
from google.auth.transport import requests
from src.job import job
from src import health
import typing
import collections
from google.oauth2 import credentials
import threading

class Tokens:
    def __init__(self):
        self.creds: typing.Optional[credentials.Credentials] = None
        self.mu = threading.Lock()
    def refresh_if_needed(self):
        """
        Refresh google oauth2 credentials if needed and the creds are present. 
        This is a thin wrapper around google.oauth2.credentials.Credentials#refresh. 
        Also checks if a refresh is needed prior to making the request.
        Uses a mutex for additional synchronization as the google's refresh method is implemented
        in a non-thread-safe manner
        """
        with self.mu:
            if self.creds == None:
                return
            # TODO: clean-up
            # None when first fetched due to the weird  
            # (flow begins with manually prepared request and 
            # creds are imported with a bare constructor)
            # way it is done, see resources/google_oauth2.py
            if self.creds.expiry \
                    and (datetime.datetime.now() - typing.cast(datetime.datetime, self.creds.expiry)) \
                    >= datetime.timedelta(minutes=1):
                # not expired or expiry sooner than a minute away 
                # (we want the token to be valid for at least the next minute so we can make requests)
                return
            self.creds.refresh(requests.Request())
    def set_creds(self, creds: credentials.Credentials):
        self.creds = creds
    def get_valid_creds(self) -> credentials.Credentials:
        self.refresh_if_needed()
        res = self.creds
        if res == None:
            raise Exception("GOAuth2 credentials are absent")
        return res

class GoogleOAuth2State:
    def __init__(self, app_oauth2_creds):
        self.user_id_to_tokens_map: typing.Mapping[str, Tokens] = collections.defaultdict(Tokens)
        self.app_oauth2_creds = app_oauth2_creds
    def get_app_creds(self):
        return self.app_oauth2_creds
    def get_tokens(self, user_id):
        return self.user_id_to_tokens_map[user_id]

T = typing.TypeVar("T")
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
        self.obj_registry = {}
        self.jobs: list[job.Job] = []
    def get_status(self) -> health.AppHealth:
        return self.status
    def get_app_token(self) -> str:
        return self.app_token
    def get_google_oauth2_state(self) -> GoogleOAuth2State:
        return self.google_oauth2_state
    def get_origin(self) -> str:
        return self.origin
    def provide_obj_as(self, cls: typing.Type[T], obj: T) -> typing.Self:
        self.obj_registry[cls] = obj
        return self
    def provide_obj(self, obj: object) -> typing.Self:
        self.obj_registry[type(obj)] = obj
        return self
    def get_obj(self, cls: typing.Type[T]) -> T:
        if cls not in self.obj_registry:
            raise Exception(f"{cls} object not in registry")
        return self.obj_registry[cls]
    def register_job(self, job_constructor: typing.Callable[["AppState"], job.Job]) -> typing.Self:
        self.jobs.append(job_constructor(self))
        return self
    def get_jobs(self):
        return self.jobs

_app_state: typing.Optional[AppState]

def set_state(state: AppState):
    global _app_state
    _app_state = state
    return _app_state

def get_state() -> AppState:
    if _app_state is None:
        raise Exception("State not yet loaded")
    return _app_state

def injected(cls: typing.Type[T]) -> T:
    def getter(state: AppState = fastapi.Depends(get_state)) -> T:
        return state.get_obj(cls)
    return fastapi.Depends(getter)

