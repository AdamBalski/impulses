#!/usr/bin/env python3
"""Scenario 15: Client SDK Usage - End-to-end with SDK."""
import sys
import time
from pathlib import Path

# Add parent directory and client-sdk to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "client-sdk"))

import requests
from utils import get_base_url, assert_true, wait_for_health

# Import the SDK
from impulses_sdk import ImpulsesClient, Datapoint, DatapointSeries


def test_sdk_usage():
    """Test complete workflow using the Impulses SDK."""
    base_url = get_base_url()
    wait_for_health(base_url)
    session = requests.Session()
    
    # Step 1: Create user and token (using requests directly)
    user_email = f"test_sdk_{int(time.time())}@example.com"
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
    
    token_name = f"sdk-token-{int(time.time())}"
    resp = session.post(
        f"{base_url}/token",
        json={"name": token_name, "capability": "SUPER", "expires_at": int(time.time()) + 3600}
    )
    assert_true(resp.status_code == 200, "Token created")
    token_plaintext = resp.json().get("token_plaintext")
    assert_true(token_plaintext is not None, "Token plaintext returned")
    
    # Step 2: Initialize SDK client
    try:
        client = ImpulsesClient(
            url=base_url,
            token_value=token_plaintext,
            timeout=10
        )
        print("[OK] SDK client initialized successfully")
    except Exception as e:
        assert_true(False, f"Failed to initialize SDK client: {e}")
    
    # Step 3: Upload datapoints using SDK
    metric_name = f"sdk_test_metric_{int(time.time())}"
    
    try:
        datapoints = [
            Datapoint(
                timestamp=int(time.time() * 1000),
                value=42.0,
                dimensions={"source": "sdk", "env": "test"}
            ),
            Datapoint(
                timestamp=int(time.time() * 1000) + 1000,
                value=99.5,
                dimensions={"source": "sdk", "env": "prod"}
            ),
            Datapoint(
                timestamp=int(time.time() * 1000) + 2000,
                value=123.75,
                dimensions={"source": "sdk", "env": "dev"}
            )
        ]
        
        series = DatapointSeries(series=datapoints)
        client.upload_datapoints(metric_name, series)
        print(f"[OK] Uploaded {len(datapoints)} datapoints via SDK")
    except Exception as e:
        assert_true(False, f"Failed to upload datapoints: {e}")
    
    # Step 4: List metrics using SDK
    try:
        metrics = client.list_metric_names()
        assert_true(isinstance(metrics, list), "List metrics returns list")
        assert_true(metric_name in metrics, f"Uploaded metric '{metric_name}' in list")
        print(f"[OK] Listed {len(metrics)} metrics via SDK")
    except Exception as e:
        assert_true(False, f"Failed to list metrics: {e}")
    
    # Step 5: Fetch datapoints using SDK
    try:
        fetched_series = client.fetch_datapoints(metric_name)
        assert_true(isinstance(fetched_series, DatapointSeries), "Fetch returns DatapointSeries")
        assert_true(len(fetched_series) == 3, f"Fetched 3 datapoints (got {len(fetched_series)})")
        
        # Verify datapoint values
        values = [dp.value for dp in fetched_series]
        assert_true(42.0 in values, "First value (42.0) present")
        assert_true(99.5 in values, "Second value (99.5) present")
        assert_true(123.75 in values, "Third value (123.75) present")
        
        print(f"[OK] Fetched {len(fetched_series)} datapoints via SDK")
    except Exception as e:
        assert_true(False, f"Failed to fetch datapoints: {e}")
    
    # Step 6: Test SDK data operations (filter, map)
    try:
        # Filter: only datapoints with value > 50
        filtered = fetched_series.filter(lambda dp: dp.value > 50)
        assert_true(len(filtered) == 2, f"Filtered series has 2 datapoints (got {len(filtered)})")
        
        # Map: multiply all values by 2
        mapped = fetched_series.map(lambda dp: Datapoint(dp.timestamp, dp.value * 2, dp.dimensions))
        assert_true(len(mapped) == 3, f"Mapped series has 3 datapoints (got {len(mapped)})")
        mapped_values = [dp.value for dp in mapped]
        assert_true(84.0 in mapped_values, "Mapped value (42*2=84) present")
        assert_true(199.0 in mapped_values, "Mapped value (99.5*2=199) present")
        
        print("[OK] SDK data operations (filter, map) work correctly")
    except Exception as e:
        assert_true(False, f"Failed SDK data operations: {e}")
    
    # Step 7: Upload more datapoints and fetch again
    try:
        more_datapoints = [
            Datapoint(
                timestamp=int(time.time() * 1000) + 3000,
                value=200.0,
                dimensions={"source": "sdk", "batch": "2"}
            )
        ]
        more_series = DatapointSeries(series=more_datapoints)
        client.upload_datapoints(metric_name, more_series)
        
        # Fetch again
        updated_series = client.fetch_datapoints(metric_name)
        assert_true(len(updated_series) == 4, f"Updated series has 4 datapoints (got {len(updated_series)})")
        
        print("[OK] Incremental upload and fetch works correctly")
    except Exception as e:
        assert_true(False, f"Failed incremental operations: {e}")
    
    # Step 8: Delete metric using SDK
    try:
        client.delete_metric_name(metric_name)
        
        # Verify metric is gone
        metrics_after = client.list_metric_names()
        assert_true(metric_name not in metrics_after, "Deleted metric not in list")
        
        print("[OK] Deleted metric via SDK")
    except Exception as e:
        assert_true(False, f"Failed to delete metric: {e}")
    
    # Step 9: Test SDK with empty metric (edge case)
    empty_metric = f"empty_metric_{int(time.time())}"
    try:
        empty_series = DatapointSeries(series=[])
        client.upload_datapoints(empty_metric, empty_series)
        
        fetched_empty = client.fetch_datapoints(empty_metric)
        assert_true(len(fetched_empty) == 0, "Empty metric has 0 datapoints")
        
        print("[OK] SDK handles empty metrics correctly")
    except Exception as e:
        assert_true(False, f"Failed empty metric test: {e}")
    
    # Cleanup
    session.delete(f"{base_url}/user")
    
    print("[OK] Client SDK fully functional and integrated")


def main():
    print("== Scenario 15: Client SDK Usage ==")
    test_sdk_usage()
    print("All checks passed.")


if __name__ == "__main__":
    main()
