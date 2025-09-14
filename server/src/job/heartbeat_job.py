import logging
from src.job import job

class HeartbeatJob(job.Job):
    def run(self):
        logging.debug("Heartbeat: app is up")
    def interval(self) -> int:
        return 60


