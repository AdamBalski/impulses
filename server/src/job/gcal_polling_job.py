from src.job import job
from src import state

class GCalPollingJob(job.Job):
    def __init__(self, state: state.AppState):
        super().__init__(state)
        self.google_oauth2_state = state.get_google_oauth2_state()
    def run(self):
        pass
