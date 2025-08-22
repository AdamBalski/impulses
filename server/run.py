import os
import datetime
import bcrypt
import time
import logging
import signal

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

running = True
def shutdown_handler(signum, frame):
    _ = frame
    global running
    logging.info(f"Received signal {signum}, shutting down...")
    running = False

# Handle SIGINT and SIGTERM, but not SIGHUP
signal.signal(signal.SIGINT, shutdown_handler)
signal.signal(signal.SIGTERM, shutdown_handler)

def main():
    token = get_token_from_env()

    while running:
        logging.info("Heartbeat")
        time.sleep(1)
    logging.info("Server stopped gracefully.")

if __name__ == "__main__":
    main()

