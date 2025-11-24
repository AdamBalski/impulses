"""Impulses SDK Client with comprehensive error handling."""
import requests
import logging

from . import models
from . import exceptions

logger = logging.getLogger(__name__)

class ImpulsesClient:
    """Client for interacting with Impulses API.
    
    Args:
        url: Base URL of the Impulses API (e.g., 'http://localhost:8000')
        token_value: Plaintext value of the data token
        timeout: Request timeout in seconds (default: 3)
    
    Raises:
        ValueError: If url or token_value is empty
    
    Example:
        >>> client = ImpulsesClient(
        ...     url="http://localhost:8000",
        ...     token_value="abc123xyz"
        ... )
        >>> metrics = client.list_metric_names()
    """

    def __init__(self, url: str, token_value: str, timeout: int = 3):
        if not url:
            raise ValueError("url must not be empty")
        if not token_value:
            raise ValueError("token_value must not be empty")
        
        self.url = url.rstrip("/")  # Remove trailing slash if present
        self.token_value = token_value
        self.timeout = timeout
        
        self.headers = {
            "X-Data-Token": f"{self.token_value}",
            "Content-Type": "application/json",
        }
        
        logger.info(f"Initialized ImpulsesClient for {self.url}")
    
    def _handle_response(self, response: requests.Response, operation: str):
        """Handle HTTP response and raise appropriate exceptions.
        Raises:
            AuthenticationError: For 401 status codes
            AuthorizationError: For 403 status codes
            NotFoundError: For 404 status codes
            ValidationError: For 422 status codes
            ServerError: For 5xx status codes
            ImpulsesError: For other error status codes
        """
        if response.status_code < 400:
            return  # Success
        
        # Try to extract error detail from response
        error_detail = None
        try:
            error_data = response.json()
            error_detail = error_data.get("detail", str(error_data))
        except Exception:
            error_detail = response.text or response.reason
        
        error_msg = f"{operation} failed: {error_detail}"
        
        if response.status_code == 401:
            logger.error(f"Authentication failed: {error_detail}")
            raise exceptions.AuthenticationError(error_msg)
        elif response.status_code == 403:
            logger.error(f"Authorization failed (insufficient capability): {error_detail}")
            raise exceptions.AuthorizationError(error_msg)
        elif response.status_code == 404:
            logger.error(f"Resource not found: {error_detail}")
            raise exceptions.NotFoundError(error_msg)
        elif response.status_code == 422:
            logger.error(f"Validation error: {error_detail}")
            raise exceptions.ValidationError(error_msg)
        elif response.status_code >= 500:
            logger.error(f"Server error: {error_detail}")
            raise exceptions.ServerError(error_msg)
        else:
            logger.error(f"Unexpected error (status {response.status_code}): {error_detail}")
            raise exceptions.ImpulsesError(error_msg)
    
    def list_metric_names(self) -> list[str]:
        """List all metric names accessible by this token.

        Example:
            >>> metrics = client.list_metric_names()
            >>> print(metrics)
            ['cpu.usage', 'memory.used', 'requests.count']
        """
        try:
            logger.debug("Listing metric names")
            resp = requests.get(
                f"{self.url}/data",
                headers=self.headers,
                timeout=self.timeout
            )
            self._handle_response(resp, "List metric names")
            return resp.json()
        except requests.exceptions.Timeout:
            raise exceptions.NetworkError(f"Request timed out after {self.timeout}s")
        except requests.exceptions.ConnectionError as e:
            raise exceptions.NetworkError(f"Connection failed: {e}")
        except requests.exceptions.RequestException as e:
            raise exceptions.NetworkError(f"Network error: {e}")
    
    def fetch_datapoints(self, metric_name: str) -> models.DatapointSeries:
        """Fetch datapoints for a specific metric.

        Example:
            >>> series = client.fetch_datapoints('cpu.usage')
            >>> for dp in series:
            ...     print(f"{dp.timestamp}: {dp.value}")
        """
        if not metric_name:
            raise ValueError("metric_name must not be empty")
        
        try:
            logger.debug(f"Fetching datapoints for metric: {metric_name}")
            resp = requests.get(
                f"{self.url}/data/{metric_name}",
                headers=self.headers,
                timeout=self.timeout
            )
            self._handle_response(resp, f"Fetch datapoints for '{metric_name}'")
            data = resp.json()
            
            # Handle both list and RootModel (with 'root' field) formats
            if isinstance(data, list):
                return models.DatapointSeries.from_api_obj(data)
            else:
                raise exceptions.ImpulsesError(f"Unexpected response format: {type(data)}")
        
        except requests.exceptions.Timeout:
            raise exceptions.NetworkError(f"Request timed out after {self.timeout}s")
        except requests.exceptions.ConnectionError as e:
            raise exceptions.NetworkError(f"Connection failed: {e}")
        except requests.exceptions.RequestException as e:
            raise exceptions.NetworkError(f"Network error: {e}")
    
    def upload_datapoints(self, metric_name: str, datapoints: models.DatapointSeries) -> None:
        """Upload datapoints for a specific metric.

        Example:
            >>> from impulses_sdk.models import Datapoint, DatapointSeries
            >>> dp = Datapoint(timestamp=1234567890, value=42.0, dimensions={"env": "prod"})
            >>> series = DatapointSeries([dp])
            >>> client.upload_datapoints('cpu.usage', series)
        """
        if not metric_name:
            raise ValueError("metric_name must not be empty")
        if datapoints is None:
            raise ValueError("datapoints must not be None")
        
        try:
            logger.debug(f"Uploading {len(datapoints)} datapoints to metric: {metric_name}")
            payload = datapoints.to_api_obj()
            resp = requests.post(
                f"{self.url}/data/{metric_name}",
                headers=self.headers,
                json=payload,
                timeout=self.timeout
            )
            self._handle_response(resp, f"Upload datapoints to '{metric_name}'")
            logger.info(f"Successfully uploaded {len(datapoints)} datapoints to {metric_name}")
        
        except requests.exceptions.Timeout:
            raise exceptions.NetworkError(f"Request timed out after {self.timeout}s")
        except requests.exceptions.ConnectionError as e:
            raise exceptions.NetworkError(f"Connection failed: {e}")
        except requests.exceptions.RequestException as e:
            raise exceptions.NetworkError(f"Network error: {e}")
    
    def delete_metric_name(self, metric_name: str) -> None:
        """Delete a metric and all its datapoints.
        
        Example:
            >>> client.delete_metric_name('old.metric')
        """
        if not metric_name:
            raise ValueError("metric_name must not be empty")
        
        try:
            logger.debug(f"Deleting metric: {metric_name}")
            resp = requests.delete(
                f"{self.url}/data/{metric_name}",
                headers=self.headers,
                timeout=self.timeout
            )
            self._handle_response(resp, f"Delete metric '{metric_name}'")
            logger.info(f"Successfully deleted metric: {metric_name}")
        
        except requests.exceptions.Timeout:
            raise exceptions.NetworkError(f"Request timed out after {self.timeout}s")
        except requests.exceptions.ConnectionError as e:
            raise exceptions.NetworkError(f"Connection failed: {e}")
        except requests.exceptions.RequestException as e:
            raise exceptions.NetworkError(f"Network error: {e}")
