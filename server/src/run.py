from contextlib import asynccontextmanager
import json
import os
from apscheduler.schedulers.background import BackgroundScheduler
import fastapi
from src.resources import google_oauth2
from src import state
from src import health
import uvicorn
import datetime
import bcrypt
import asyncio
import logging

def setup_logging():
    log_filename = "./log-" + str(datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S"))
    logging.basicConfig(
        filename=log_filename,
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    os.symlink(log_filename, log_filename + "_link")
    os.replace(log_filename + "_link", "./log-latest")
setup_logging()

def get_from_env_or_fail(var: str) -> str:
    res = os.environ.get(var)
    if res:
        return res
    raise Exception(f"Env variables {var} is required, but was not supplied, failing...")

def get_token_from_env():
    token = get_from_env_or_fail("TOKEN")
    hashed_token = get_from_env_or_fail("HASHED_TOKEN")
    if bcrypt.checkpw(token.encode("utf-8"), hashed_token.encode("utf-8")):
        logging.info("App token hash verified")
        return token
    raise Exception("App token does not match its hash")

def shutdown_handler(status: health.AppHealth):
    status.status = health.HealthStatus.STOPPING
    logging.info(f"Shutting down...")
def schedule_jobs():
    scheduler = BackgroundScheduler()
    scheduler.add_job(lambda: logging.info("heartbeat"), 'cron', second='*/5')
    scheduler.start()

def main():
    global app_state
    token = get_token_from_env()
    google_oauth2_creds = json.loads(get_from_env_or_fail("GOOGLE_OAUTH2_CREDS"))
    status = health.AppHealth(health.HealthStatus.UP)

    app_state = state.set_state(state.AppState(
            status=status,
            app_token=token,
            google_oauth2_state=state.GoogleOAuth2State(google_oauth2_creds),
            origin=get_from_env_or_fail("ORIGIN")
    ))

    @asynccontextmanager
    async def lifespan(_: fastapi.FastAPI):
        schedule_jobs()
        yield
        shutdown_handler(status)
    app = fastapi.FastAPI(lifespan=lifespan, dependencies = [fastapi.Depends(state.get_state)])
    app.include_router(google_oauth2.router, prefix="/oauth2/google")


    @app.get("/healthz")
    async def healthz():
        return status

    port = get_from_env_or_fail("PORT")
    config = uvicorn.Config(app, host="0.0.0.0", port=int(port), log_level="info")
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

