import abc
import uuid
import typing
import logging
import datetime

from src import state

class Job:
    def __init__(self, state: "state.AppState"):
        self.state = state
    def job_name(self) -> str:
        return type(self).__name__
    def interval(self) -> int:
        return 5 * 60
    @abc.abstractmethod
    def run(self):
        pass

    
def runner(job: Job) -> typing.Callable[[], None]:
    def __():
        job_id = uuid.uuid4()
        job_start_time = datetime.datetime.now(datetime.timezone.utc)
        logging.info(f"Starting job: {job.job_name()} at {job_start_time}. Job id: {job_id}")
        job.run()
        job_end_time = datetime.datetime.now(datetime.timezone.utc)
        logging.info(f"Finishing job: {job.job_name()} at {job_end_time}. Job took: {job_end_time - job_start_time}. Job id: {job_id}")
    return __
