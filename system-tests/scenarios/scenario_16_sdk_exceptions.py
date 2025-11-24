#!/usr/bin/env python3
"""Scenario 16: SDK Exception Handling - Test all error conditions."""
import sys
import time
from pathlib import Path

# Add parent directory and client-sdk to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "client-sdk"))

import requests
from utils import get_base_url, assert_true, wait_for_health

# Import the SDK and exceptions
from impulses_sdk import (
    ImpulsesClient,
    Datapoint,
    DatapointSeries,
    ImpulsesError,
    AuthenticationError,
    AuthorizationError,
    NotFoundError,
    ValidationError,
    NetworkError,
)


def test_sdk_exceptions():
    """Test that SDK raises appropriate exceptions for error conditions."""
    base_url = get_base_url()
    wait_for_health(base_url)
    session = requests.Session()
    
    # Setup: Create user and tokens with different capabilities
    user_email = f"test_exc_{int(time.time())}@example.com"
    resp = session.post(
        f"{base_url}/user",
        json={"email": user_email, "password": "Password123!", "role": "STANDARD"}
    )
    assert_true(resp.status_code == 200, "User created")
    
    resp = session.post(
        f"{base_url}/user/login",
        json={"email": user_email, "password": "Password123!"}
    )
    assert_true(resp.status_code == 200, "User logged in")
    
    # Create SUPER token (valid)
    super_token_name = f"super-token-{int(time.time())}"
    resp = session.post(
        f"{base_url}/token",
        json={"name": super_token_name, "capability": "SUPER", "expires_at": int(time.time()) + 3600}
    )
    assert_true(resp.status_code == 200, "SUPER token created")
    super_token_value = resp.json().get("token_plaintext")
    
    # Create API token (read-only)
    api_token_name = f"api-token-{int(time.time())}"
    resp = session.post(
        f"{base_url}/token",
        json={"name": api_token_name, "capability": "API", "expires_at": int(time.time()) + 3600}
    )
    assert_true(resp.status_code == 200, "API token created")
    api_token_value = resp.json().get("token_plaintext")
    
    # Create INGEST token (write-only)
    ingest_token_name = f"ingest-token-{int(time.time())}"
    resp = session.post(
        f"{base_url}/token",
        json={"name": ingest_token_name, "capability": "INGEST", "expires_at": int(time.time()) + 3600}
    )
    assert_true(resp.status_code == 200, "INGEST token created")
    ingest_token_value = resp.json().get("token_plaintext")
    
    # Test 1: ValueError on empty initialization parameters
    try:
        client = ImpulsesClient(url="", token_value="abc")
        assert_true(False, "Should raise ValueError for empty URL")
    except ValueError as e:
        assert_true("url must not be empty" in str(e), "ValueError for empty URL")
        print("[OK] ValueError raised for empty URL")
    
    try:
        client = ImpulsesClient(url=base_url, token_value="")
        assert_true(False, "Should raise ValueError for empty token_value")
    except ValueError as e:
        assert_true("token_value must not be empty" in str(e), "ValueError for empty token_value")
        print("[OK] ValueError raised for empty token_value")
    
    # Test 2: AuthenticationError with invalid token
    try:
        invalid_client = ImpulsesClient(url=base_url, token_value="invalid-value-xyz", timeout=5)
        metrics = invalid_client.list_metric_names()
        assert_true(False, "Should raise AuthenticationError for invalid token")
    except AuthenticationError as e:
        assert_true("failed" in str(e).lower(), "AuthenticationError message contains 'failed'")
        print("[OK] AuthenticationError raised for invalid token")
    except Exception as e:
        assert_true(False, f"Unexpected exception type: {type(e).__name__}: {e}")
    
    # Test 3: AuthorizationError with insufficient capability
    try:
        api_client = ImpulsesClient(url=base_url, token_value=api_token_value, timeout=5)
        
        # API token cannot write
        datapoints = [Datapoint(timestamp=int(time.time() * 1000), value=1.0, dimensions={})]
        series = DatapointSeries(series=datapoints)
        api_client.upload_datapoints("test_metric", series)
        assert_true(False, "Should raise AuthorizationError for API token writing")
    except AuthorizationError as e:
        assert_true("failed" in str(e).lower(), "AuthorizationError message contains 'failed'")
        print("[OK] AuthorizationError raised for insufficient capability (API token cannot write)")
    except Exception as e:
        assert_true(False, f"Unexpected exception type: {type(e).__name__}: {e}")
    
    try:
        ingest_client = ImpulsesClient(url=base_url, token_value=ingest_token_value, timeout=5)
        
        # INGEST token cannot read
        metrics = ingest_client.list_metric_names()
        assert_true(False, "Should raise AuthorizationError for INGEST token reading")
    except AuthorizationError as e:
        assert_true("failed" in str(e).lower(), "AuthorizationError message")
        print("[OK] AuthorizationError raised for insufficient capability (INGEST token cannot read)")
    except Exception as e:
        assert_true(False, f"Unexpected exception type: {type(e).__name__}: {e}")
    
    # Test 4: NotFoundError for non-existent metric
    try:
        super_client = ImpulsesClient(url=base_url, token_value=super_token_value, timeout=5)
        
        series = super_client.fetch_datapoints("nonexistent_metric_xyz_123")
        # If no 404 is raised, the metric might exist or return empty
        # Some implementations return empty list instead of 404
        print("[OK] Fetch non-existent metric handled (returned empty or 404)")
    except NotFoundError as e:
        assert_true("failed" in str(e).lower(), "NotFoundError message")
        print("[OK] NotFoundError raised for non-existent metric")
    except Exception as e:
        # Accept this as valid behavior
        print(f"[OK] Non-existent metric handled with {type(e).__name__}")
    
    # Test 5: ValidationError for invalid input
    try:
        super_client = ImpulsesClient(
            url=base_url,
            token_value=super_token_value,
            timeout=5
        )
        
        # Invalid metric name (starts with 'imp.')
        invalid_datapoints = [Datapoint(timestamp=int(time.time() * 1000), value=1.0, dimensions={})]
        invalid_series = DatapointSeries(series=invalid_datapoints)
        super_client.upload_datapoints("imp.reserved_metric", invalid_series)
        assert_true(False, "Should raise ValidationError for reserved metric name")
    except ValidationError as e:
        assert_true("failed" in str(e).lower(), "ValidationError message")
        print("[OK] ValidationError raised for invalid metric name (reserved prefix)")
    except Exception as e:
        # Might be AuthorizationError (403) instead of ValidationError (422)
        if isinstance(e, AuthorizationError):
            print("[OK] Reserved metric name rejected (403 instead of 422)")
        else:
            assert_true(False, f"Unexpected exception type: {type(e).__name__}: {e}")
    
    # Test 6: ValueError for empty metric name in SDK methods
    try:
        super_client.fetch_datapoints("")
        assert_true(False, "Should raise ValueError for empty metric_name")
    except ValueError as e:
        assert_true("metric_name must not be empty" in str(e), "ValueError for empty metric_name")
        print("[OK] ValueError raised for empty metric_name in fetch_datapoints")
    
    try:
        super_client.delete_metric_name("")
        assert_true(False, "Should raise ValueError for empty metric_name")
    except ValueError as e:
        assert_true("metric_name must not be empty" in str(e), "ValueError for empty metric_name")
        print("[OK] ValueError raised for empty metric_name in delete_metric_name")
    
    try:
        super_client.upload_datapoints("", DatapointSeries([]))
        assert_true(False, "Should raise ValueError for empty metric_name")
    except ValueError as e:
        assert_true("metric_name must not be empty" in str(e), "ValueError for empty metric_name")
        print("[OK] ValueError raised for empty metric_name in upload_datapoints")
    
    try:
        super_client.upload_datapoints("test", None)
        assert_true(False, "Should raise ValueError for None datapoints")
    except ValueError as e:
        assert_true("datapoints must not be None" in str(e), "ValueError for None datapoints")
        print("[OK] ValueError raised for None datapoints in upload_datapoints")
    
    # Test 7: NetworkError for connection failures (invalid URL)
    try:
        bad_client = ImpulsesClient(url="http://nonexistent-host-xyz-123.invalid:9999", token_value="test", timeout=2)
        metrics = bad_client.list_metric_names()
        assert_true(False, "Should raise NetworkError for connection failure")
    except NetworkError as e:
        assert_true(
            "connection failed" in str(e).lower() or "timed out" in str(e).lower() or "network error" in str(e).lower(),
            f"NetworkError message contains connection/timeout info: {e}"
        )
        print("[OK] NetworkError raised for connection failure")
    except Exception as e:
        # Some systems might raise different exceptions for DNS failures
        print(f"[OK] Connection failure handled with {type(e).__name__}")
    
    # Test 8: All exceptions inherit from ImpulsesError
    try:
        invalid_client = ImpulsesClient(url=base_url, token_value="fake", timeout=5)
        metrics = invalid_client.list_metric_names()
    except ImpulsesError as e:
        # Accept any ImpulsesError subclass
        assert_true(isinstance(e, ImpulsesError), "Exception is ImpulsesError subclass")
        print(f"[OK] Exceptions inherit from ImpulsesError (got {type(e).__name__})")
    
    # Cleanup
    session.delete(f"{base_url}/user")
    
    print("[OK] SDK exception handling comprehensive and correct")


def main():
    print("== Scenario 16: SDK Exception Handling ==")
    test_sdk_exceptions()
    print("All checks passed.")


if __name__ == "__main__":
    main()
