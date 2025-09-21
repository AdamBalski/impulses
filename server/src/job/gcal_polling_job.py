import datetime
import threading
import typing
import logging
import pydantic

from src.db import Dao
from src.job import job
from src import state

from google.oauth2 import credentials
from googleapiclient import discovery

class Event(pydantic.BaseModel):
    event_id: str
    summary: str
    description: str
    start: datetime.datetime
    end: datetime.datetime
class GCalEventsPerUserData(pydantic.BaseModel):
    events: typing.Dict[str, Event]
    lastSyncToken: typing.Optional[str] = None
    @staticmethod
    def empty():
        return GCalEventsPerUserData({}, None)
GCalEventsPerUserDataType = Dao.Type.for_pydantic_model(GCalEventsPerUserData, GCalEventsPerUserData.empty)

class GCalPollingJob(job.Job):
    def __init__(self, state: state.AppState):
        super().__init__(state)
        db_dao = state.get_obj(Dao.PersistentDao)
        self.events_dao = Dao.TypedPersistentDao(db_dao, GCalEventsPerUserDataType)
        self.google_oauth2_state = state.get_google_oauth2_state()
        self.mu = threading.Lock()
    def poll_for_user(self, user_id: str, tokens: state.Tokens):
        logging.debug(f"Fetching gCal events for user {user_id}")
        # tokens are fresh here (refreshed ad-hoc during get_valid_creds)
        creds = tokens.get_valid_creds()

        data = self.events_dao.read(f"gcal_events_data#{user_id}")

        # poll for new events
        changes = self.poll_events(creds, data.lastSyncToken)

        # upsert the new events via a side-effect
        self.apply_changes(data, changes)

        self.events_dao.flush(f"gcal_events_data#{user_id}", data)
        pass
    def run(self):
        try:
            if not self.mu.acquire(blocking=False):
                logging.warning("Not running another g cal polling job as the previous run hasn't finished")
            for user_id, tokens in self.google_oauth2_state.user_id_to_tokens_map.items():
                try:
                    self.poll_for_user(user_id, tokens)
                except Exception as e:
                    logging.warning(f"Exception happened during gcal polling for user: {user_id}", e)
        finally:
            self.mu.release()
    def poll_events(self, creds: credentials.Credentials, last_sync_token: typing.Optional[str]) \
            -> typing.Optional[list[dict]]:
        """
        Polls for events and returns them as list in google api form if the poll was successful. 
        Includes tombstone events.
        """
        gcal_client = discovery.build("calendar", "v3", credentials=creds)
        try:
            result = []
            nextPageToken = None
            nextSyncToken = None
            while not nextSyncToken:
                curr_res = gcal_client.list(calendarId="primary", 
                                            pageToken=nextPageToken, 
                                            syncToken=last_sync_token).execute()
                for event in curr_res.get("items", []):
                    if event.get("kind", "unknown type of event") != "calendar#event":
                        continue
                    result.append(event)
                nextSyncToken = curr_res.get("nextSyncToken", None)
                nextPageToken = curr_res.get("nextPageToken", None)
                # should send the last sync token only on the first request
                last_sync_token = None
            logging.debug(f"Fetched {len(result)} events")
        except Exception as e:
            logging.warning("Exception ocurred during actual events fetching", e)
    def apply_changes(self, data: GCalEventsPerUserData, changes: typing.Optional[list[dict]]):
        # an error during poll ocurred, possibly the lastSyncToken expired, 
        # should do full-sync on the next job run
        if changes == None:
            data.lastSyncToken = None
            return
        for event in changes:
            status = event["status"]
            eid = event["id"]
            # tombstone event
            if status == "cancelled":
                data.events.pop(eid, "ignore event not found error")
                continue
            summary = event["summary"]
            description = event.get("description", "")
            start = event["start"]["dateTime"]
            end = event["end"]["dateTime"]
            data.events[eid] = Event(eid, summary, description, start, end)

    def safe_release_lock(self):
        try:
            self.mu.release()
        # unlocking an unlocked lock raises an exception
        except RuntimeError:
            pass
