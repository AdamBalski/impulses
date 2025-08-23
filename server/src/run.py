from contextlib import asynccontextmanager
import os
from apscheduler.schedulers.background import BackgroundScheduler
import fastapi
import uvicorn
import datetime
import bcrypt
import asyncio
import logging
import health

logging.basicConfig(
    filename="./log-" + str(datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

def get_token_from_env():
    token = os.environ.get("TOKEN")
    hashed_token = os.environ.get("HASHED_TOKEN")
    if token and hashed_token \
            and bcrypt.checkpw(token.encode("utf-8"), hashed_token.encode("utf-8")):
        logging.info("App token hash verified")
        return token
    msg = "App token does not match its hash or either the hashed or original token was not supplied"
    logging.error(msg)
    raise Exception(msg)

def shutdown_handler(status: health.AppHealth):
    status.status = health.HealthStatus.STOPPING
    logging.info(f"Shutting down...")
def schedule_jobs():
    scheduler = BackgroundScheduler()
    scheduler.add_job(lambda: logging.info("heartbeat"), 'cron', second='*/5')
    scheduler.start()

def main():
    token = get_token_from_env()
    status = health.AppHealth(health.HealthStatus.UP)
    @asynccontextmanager
    async def lifespan(app: fastapi.FastAPI):
        schedule_jobs()
        yield
        shutdown_handler(status)
    app = fastapi.FastAPI(lifespan=lifespan)


    @app.get("/healthz")
    async def healthz():
        return status

    config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(config)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    loop.run_until_complete(server.serve())

if __name__ == "__main__":
    main()

