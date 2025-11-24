import collections
from contextlib import nullcontext
import datetime
import threading
import typing
import logging
import pydantic
import re
import time

from src.dao import data_dao
from src.dao.gcal_dao import GCalDao, GCalCredentials, GCalEvent, GCalEventState
from src.dao.token_repo import TokenRepo
from src.db import dao
from src.job import job
from src.common import state

from google.oauth2 import credentials
from google.auth.transport.requests import Request
from googleapiclient import discovery

class Event(pydantic.BaseModel):
    event_id: str
    summary: str
    description: str
    start: str
    end: str
class GCalEventsPerUserData(pydantic.BaseModel):
    events: typing.Dict[str, Event]
    lastSyncToken: typing.Optional[str] = None
    @staticmethod
    def empty():
        return GCalEventsPerUserData(events={}, lastSyncToken=None)
GCalEventsPerUserDataType = dao.Type.for_pydantic_model(GCalEventsPerUserData, GCalEventsPerUserData.empty)

class GCalPollingJob(job.Job):
    def __init__(self, state: state.AppState):
        super().__init__(state)
        self.data_dao = state.get_obj(data_dao.DataDao)
        self.gcal_dao = state.get_obj(GCalDao)
        self.token_repo = state.get_obj(TokenRepo)
        self.google_oauth2_state = state.get_google_oauth2_state()
        self.mu = threading.Lock()
    
    def interval(self) -> int:
        return 5 * 60
    
    def run(self):
        """Poll Google Calendar for all token-authorized users."""
        if not self.mu.acquire(blocking=False):
            logging.warning("Not running another GCal polling job as the previous run hasn't finished")
            return
        
        try:
            # Get all GCal credentials from file storage
            all_credentials = self.gcal_dao.list_all_credentials()
            
            if not all_credentials:
                logging.debug("No active Google Calendar integrations")
                return
            
            # Filter to only active (non-expired) tokens
            active_creds = []
            for creds in all_credentials:
                token = self.token_repo.get_token_by_id(creds.token_id)
                if token and token.expires_at > int(time.time()):
                    active_creds.append((creds, token))
                else:
                    logging.debug(f"Skipping expired/deleted token {creds.token_id}")
            
            logging.info(f"Polling {len(active_creds)} active Google Calendar integrations")
            
            for creds, token in active_creds:
                try:
                    self.poll_calendar_for_token(creds, token)
                except Exception as e:
                    logging.error(f"Error polling calendar for token {creds.token_id}: {e}")
        finally:
            self.mu.release()
    
    def poll_calendar_for_token(self, creds: GCalCredentials, token):
        """Poll a single token's calendar."""
        logging.debug(f"Fetching GCal events for token {creds.token_id} (user {creds.user_id})")
        
        # Build Google credentials
        google_creds = credentials.Credentials(
            token=creds.access_token,
            refresh_token=creds.refresh_token,
            token_uri=self.google_oauth2_state.get_app_creds()["web"]["token_uri"],
            client_id=self.google_oauth2_state.get_app_creds()["web"]["client_id"],
            client_secret=self.google_oauth2_state.get_app_creds()["web"]["client_secret"],
            scopes=['https://www.googleapis.com/auth/calendar.readonly']
        )
        
        # Refresh if expired
        if google_creds.expired and google_creds.refresh_token:
            try:
                google_creds.refresh(Request())
                # Update stored credentials
                self.gcal_dao.store_credentials(
                    token_id=creds.token_id,
                    user_id=creds.user_id,
                    access_token=google_creds.token,
                    refresh_token=google_creds.refresh_token,
                    token_expiry=int(google_creds.expiry.timestamp())
                )
                logging.debug(f"Refreshed GCal credentials for token {creds.token_id}")
            except Exception as e:
                logging.error(f"Failed to refresh credentials for token {creds.token_id}: {e}")
                return
        
        # Load full event state
        event_state = self.gcal_dao.get_event_state(creds.token_id)
        
        # Get sync state
        sync_state = self.gcal_dao.get_sync_state(creds.token_id)
        last_sync_token = sync_state.sync_token if sync_state else None
        
        # Poll for changes (incremental)
        changes_and_next_token = self.poll_events(google_creds, last_sync_token)
        
        if changes_and_next_token is None:
            # Error during poll, clear sync token to force full sync next time
            if sync_state:
                self.gcal_dao.update_sync_state(
                    token_id=creds.token_id,
                    calendar_id='primary',
                    sync_token=None
                )
            return
        
        changes, next_sync_token = changes_and_next_token
        
        # Apply incremental changes to full event state
        self.apply_changes_to_state(event_state, changes)
        
        # Save updated event state
        self.gcal_dao.save_event_state(event_state)
        
        # Generate metrics from FULL event state (not just changes!)
        metrics_dps = self.generate_metrics_from_state(event_state)
        
        # Delete ALL imp.events.* metrics to prevent orphaned metrics from deleted events
        all_metric_names = self.data_dao.list_metric_names(creds.user_id)
        for metric_name in all_metric_names:
            if metric_name.startswith("imp.events."):
                self.data_dao.delete_metric_name(creds.user_id, metric_name)
        
        # Write current metrics (only for active events)
        for metric_name, dps_list in metrics_dps.items():
            self.data_dao.add(creds.user_id, metric_name, dps_list)
        
        # Update sync state
        if next_sync_token:
            self.gcal_dao.update_sync_state(
                token_id=creds.token_id,
                calendar_id='primary',
                sync_token=next_sync_token
            )
        
        logging.info(f"Successfully polled calendar for user {creds.user_id} via token {creds.token_id} ({len(event_state.events)} total events)")
    
    def apply_changes_to_state(self, event_state: GCalEventState, changes: list[dict]) -> None:
        """Apply incremental changes to full event state."""
        for event in changes:
            event_id = event["id"]
            status = event.get("status")
            
            # Tombstone event - remove from state
            if status == "cancelled":
                event_state.events.pop(event_id, None)
                logging.debug(f"Removed cancelled event {event_id}")
                continue
            
            # Add or update event in state
            summary = event.get("summary", "")
            description = event.get("description", "")
            start = self.get_date(event.get("start", {}))
            end = self.get_date(event.get("end", {}))
            
            if start and end:
                event_state.events[event_id] = GCalEvent(
                    event_id=event_id,
                    summary=summary,
                    description=description,
                    start=start,
                    end=end
                )
                logging.debug(f"Updated event {event_id}: {summary}")
    
    def generate_metrics_from_state(self, event_state: GCalEventState) -> dict[str, list[data_dao.DatapointDto]]:
        """Generate metrics from full event state (all events)."""
        metrics_dps = collections.defaultdict(lambda: [])
        events_synchronized = 0
        
        for event_id, event in event_state.events.items():
            # Only process events with #! prefix
            if not event.summary.startswith("#!"):
                continue
            
            events_synchronized += 1
            dims = {"src": event_id, "activity": event.summary[2:]}
            
            # Parse start/end times
            try:
                start_dt = datetime.datetime.fromisoformat(event.start)
                end_dt = datetime.datetime.fromisoformat(event.end)
            except ValueError as e:
                logging.warning(f"Invalid date format for event {event_id}: {e}")
                continue
            
            duration_millis = (end_dt - start_dt) / datetime.timedelta(milliseconds=1)
            timestamp_millis = int(1000 * start_dt.timestamp())
            custom_values = {}
            
            # Parse description for dimensions and custom metrics
            for line in event.description.splitlines():
                valid_symbol = r" *([A-Za-z0-9._]+) *"
                if m := re.match(f"{valid_symbol}:{valid_symbol}", line):
                    dims[m.group(1)] = m.group(2)
                elif m := re.match(f"{valid_symbol}= *([0-9.]*) *", line):
                    try:
                        custom_values[m.group(1)] = float(m.group(2))
                    except ValueError as e:
                        logging.debug(f"Couldn't parse metric value: {e}")
            
            # Create duration datapoint
            new_dp = data_dao.DatapointDto(
                timestamp=timestamp_millis,
                dimensions=dims,
                value=duration_millis
            )
            metrics_dps["imp.events.duration"].append(new_dp)
            
            # Create custom metric datapoints
            for name, value in custom_values.items():
                new_dp = data_dao.DatapointDto(
                    timestamp=timestamp_millis,
                    dimensions=dims,
                    value=value
                )
                metrics_dps["imp.events.custom." + name].append(new_dp)
        
        logging.debug(f"Generated metrics from {events_synchronized} events")
        return dict(metrics_dps)

    def poll_events(self, creds: credentials.Credentials, last_sync_token: typing.Optional[str]) \
            -> typing.Optional[typing.Tuple[list[dict], str]]:
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
                curr_res = gcal_client.events().list(calendarId="primary", 
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
            return result, nextSyncToken
        except Exception as e:
            logging.warning("Exception occurred during actual events fetching", e)
            return None
    
    def get_date(self, gcal_api_time_info) -> str | None:
        """Extract date/time from Google Calendar API time info."""
        if not gcal_api_time_info:
            return None
        if "date" in gcal_api_time_info:
            # TODO: default timezone should be configurable
            return gcal_api_time_info["date"] + "T00:00:00+00:00"
        return gcal_api_time_info.get("dateTime")


    def safe_release_lock(self):
        try:
            self.mu.release()
        # unlocking an unlocked lock raises an exception
        except RuntimeError:
            pass
