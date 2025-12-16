import asyncio
import bcrypt
import datetime
import fastapi
import json
import logging
import os
import pathlib
import sys
import uvicorn
from apscheduler.schedulers.background import BackgroundScheduler
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware

from src.common import health
from src.common import state
from src.dao import data_dao
from src.db import dao
from src.db import pg as dbpg
from src.dao import user_repo, token_repo
from src.resources import data
from src.resources import google_oauth2
from src.resources import user
from src.resources import token
from src.job import job
from src.job import heartbeat_job
from src.job.gcal_sync import gcal_polling_job
from src.auth.session import SessionStore
from src.auth.token_cache import TokenCache
from src.dao.gcal_dao import GCalDao

def setup_logging():
    log_filename = "./log-" + str(datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S"))
    logging.basicConfig(
        filename=log_filename,
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )
    logging.getLogger().addHandler(logging.StreamHandler(sys.stdout))

    os.symlink(log_filename, log_filename + "_link")
    os.replace(log_filename + "_link", "./log-latest")
setup_logging()

def get_from_env_or_fail(var: str) -> str:
    res = os.environ.get(var)
    if res:
        return res
    raise Exception(f"Env variables {var} is required, but was not supplied, failing...")

def shutdown_handler(status: health.AppHealth):
    status.status = health.HealthStatus.STOPPING
    logging.info(f"Shutting down...")
def schedule_jobs(jobs: list[job.Job]):
    scheduler = BackgroundScheduler()
    for job_obj in jobs:
        runner_fn = job.runner(job_obj)
        scheduler.add_job(runner_fn, 'date', run_date=datetime.datetime.now(datetime.timezone.utc))
        scheduler.add_job(runner_fn, 'interval', seconds=job_obj.interval())
    scheduler.start()

def main():
    global app_state
    google_oauth2_creds = json.loads(get_from_env_or_fail("GOOGLE_OAUTH2_CREDS"))
    status = health.AppHealth(health.HealthStatus.UP)
    db_dao = dao.PersistentDao(pathlib.Path("./data-store"))
    pg_conn_json = get_from_env_or_fail("POSTGRES_CONN_JSON")
    pg_pool = dbpg.connect_from_json(pg_conn_json)
    session_ttl_sec = int(os.environ.get("SESSION_TTL_SEC", "1800"))
    session_store = SessionStore(ttl_seconds=session_ttl_sec)
    
    # Initialize token cache and load from database
    token_cache = TokenCache()
    token_repository = token_repo.TokenRepo(pg_pool)
    token_cache.load_from_db(token_repository)
    logging.info(f"Loaded {token_cache.size()} active tokens into cache")
    
    # Initialize GCalDao with file-based storage
    gcal_dao = GCalDao(db_dao)

    app_state = state.set_state(state.AppState(
            status=status,
            google_oauth2_state=state.GoogleOAuth2State(google_oauth2_creds),
            api_origin=get_from_env_or_fail("ORIGIN_API"),
            ui_origin=get_from_env_or_fail("ORIGIN")
    )) \
        .provide_obj(data_dao.DataDao(db_dao)) \
        .provide_obj(db_dao) \
        .provide_obj(pg_pool) \
        .provide_obj(user_repo.UserRepo(pg_pool)) \
        .provide_obj(token_repository) \
        .provide_obj(session_store) \
        .provide_obj(token_cache) \
        .provide_obj(gcal_dao) \
        .register_job(heartbeat_job.HeartbeatJob) \
        .register_job(gcal_polling_job.GCalPollingJob)


    @asynccontextmanager
    async def lifespan(_: fastapi.FastAPI):
        schedule_jobs(app_state.get_jobs())
        yield
        shutdown_handler(status)
    app = fastapi.FastAPI(lifespan=lifespan, dependencies = [fastapi.Depends(state.get_state)])
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[get_from_env_or_fail("ORIGIN")],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-Requested-With",
                       "Accept", "Origin", "Referer", "User-Agent", "Cache-Control",
                       "Pragma", "Expires", "X-Data-Token"],
    )
    
    app.include_router(google_oauth2.router, prefix="/oauth2/google")
    app.include_router(data.router, prefix="/data")
    app.include_router(user.router, prefix="/user")
    app.include_router(token.router, prefix="/token")


    @app.get("/healthz")
    async def healthz():
        return status

    port = get_from_env_or_fail("PORT")
    config = uvicorn.Config(
        app, 
        host="0.0.0.0", 
        port=int(port), 
        log_level="debug",
        log_config=None,
        access_log=True
    )
    server = uvicorn.Server(config)


    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)


    loop.run_until_complete(server.serve())

    # suppress unused
    _ = healthz

if __name__ == "__main__":
    try:
        main()
    except BaseException:
        logging.exception(f"Exception raised, quitting...")
        raise

