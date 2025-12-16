import typing

import fastapi

from src.common import health
from src.job import job
from src.job.gcal_sync.gcal_state import GoogleOAuth2State

T = typing.TypeVar("T")

class AppState:
    def __init__(self,
                 status: health.AppHealth,
                 google_oauth2_state: GoogleOAuth2State,
                 api_origin: str,
                 ui_origin: str):
        self.status = status
        self.google_oauth2_state = google_oauth2_state
        self.api_origin = api_origin
        self.ui_origin = ui_origin
        self.obj_registry = {}
        self.jobs: list[job.Job] = []
    def get_status(self) -> health.AppHealth:
        return self.status
    def get_google_oauth2_state(self) -> GoogleOAuth2State:
        return self.google_oauth2_state
    def get_api_origin(self) -> str:
        return self.api_origin
    def get_ui_origin(self) -> str:
        return self.ui_origin
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
