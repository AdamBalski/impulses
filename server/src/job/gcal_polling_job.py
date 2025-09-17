import logging

from src.job import job
from src import state

class GCalPollingJob(job.Job):
    def __init__(self, state: state.AppState):
        super().__init__(state)
        self.google_oauth2_state = state.get_google_oauth2_state()
    def run(self):
        for user_id, tokens in self.google_oauth2_state.user_id_to_tokens_map.items():
            def poll_for_user(user_id, tokens):
                pass
    def poll_for_user(user_id: str, tokens: state.Tokens):
        logging.debug(f"Fetching gCal events for user {user_id}")
        pass
