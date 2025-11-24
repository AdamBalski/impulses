import collections
import datetime
import threading
import typing

from google.auth.transport import requests
from google.oauth2 import credentials


class Tokens:
    def __init__(self):
        self.creds: typing.Optional[credentials.Credentials] = None
        self.mu = threading.Lock()
    def refresh_if_needed(self):
        """
        Refresh google oauth2 credentials if needed and the creds are present.
        Also checks if a refresh is needed prior to making the request.
        Uses a mutex for synchronization because google's refresh is not thread-safe.
        """
        with self.mu:
            if self.creds is None:
                return
            if self.creds.expiry:
                expiry = typing.cast(datetime.datetime, self.creds.expiry)
                # keep a 1-minute margin so callers get a token that remains valid
                # during the immediate next request(s)
                if (expiry - datetime.datetime.now()) >= datetime.timedelta(minutes=1):
                    return
            self.creds.refresh(requests.Request())
    def set_creds(self, creds: credentials.Credentials):
        self.creds = creds
    def get_valid_creds(self) -> credentials.Credentials:
        self.refresh_if_needed()
        res = self.creds
        if res is None:
            raise Exception("GOAuth2 credentials are absent")
        return res

class GoogleOAuth2State:
    def __init__(self, app_oauth2_creds):
        self.user_id_to_tokens_map: typing.Mapping[str, Tokens] = collections.defaultdict(Tokens)
        self.app_oauth2_creds = app_oauth2_creds
    def get_app_creds(self):
        return self.app_oauth2_creds
    def get_tokens(self, user_id):
        return self.user_id_to_tokens_map[user_id]
