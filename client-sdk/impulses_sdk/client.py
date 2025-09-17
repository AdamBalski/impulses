from . import models
import requests

class ImpulsesClient:
    def __init__(self, url, token):
        self.url = url
        self.token = token
        self.headers = {
            "X-Token": f"{self.token}",
            "Content-Type": "application/json",
        }
    def list_metric_names(self) -> list[str]:
        resp = requests.get(f"{self.url}/data", headers=self.headers)
        resp.raise_for_status()
        return resp.json()
    def fetch_datapoints(self, metric_name: str) -> models.DatapointSeries:
        resp = requests.get(f"{self.url}/data/{metric_name}", headers=self.headers)
        resp.raise_for_status()
        data = resp.json()
        return models.DatapointSeries.from_api_obj(data)
    def upload_datapoints(self, metric_name: str, datapoints: models.DatapointSeries) -> None:
        payload = datapoints.to_api_obj()
        resp = requests.post(f"{self.url}/data/{metric_name}", headers=self.headers, json=payload)
        resp.raise_for_status()
