#!/usr/bin/env python3
"""Scenario 18: SDK Fluent API - Test sliding_window and prefix_op as methods."""
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


def test_fluent_api():
    """Test fluent API for sliding_window and prefix_op."""
    base_url = get_base_url()
    wait_for_health(base_url)
    session = requests.Session()
    
    # Setup: Create user and token
    user_email = f"test_fluent_{int(time.time())}@example.com"
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
    
    token_name = f"fluent-token-{int(time.time())}"
    resp = session.post(
        f"{base_url}/token",
        json={"name": token_name, "capability": "SUPER", "expires_at": int(time.time()) + 3600}
    )
    assert_true(resp.status_code == 200, "Token created")
    token_plaintext = resp.json().get("token_plaintext")
    
    # Initialize SDK client
    client = ImpulsesClient(
        url=base_url,
        token_value=token_plaintext
    )
    
    # Create test data with timestamps spread over time
    base_time = int(time.time() * 1000)
    metric_name = f"fluent_test_{int(time.time())}"
    
    datapoints = [
        Datapoint(timestamp=base_time, value=10.0, dimensions={}),
        Datapoint(timestamp=base_time + 1000, value=20.0, dimensions={}),
        Datapoint(timestamp=base_time + 2000, value=30.0, dimensions={}),
        Datapoint(timestamp=base_time + 3000, value=40.0, dimensions={}),
        Datapoint(timestamp=base_time + 4000, value=50.0, dimensions={}),
    ]
    
    series = DatapointSeries(series=datapoints)
    client.upload_datapoints(metric_name, series)
    
    # Fetch the data
    fetched = client.fetch_datapoints(metric_name)
    assert_true(len(fetched) == 5, f"Fetched 5 datapoints (got {len(fetched)})")
    
    # Test 1: Fluent prefix_op (cumulative sum)
    try:
        cumulative = fetched.prefix_op(sum)
        assert_true(isinstance(cumulative, DatapointSeries), "prefix_op returns DatapointSeries")
        assert_true(len(cumulative) == 5, f"Cumulative has 5 datapoints (got {len(cumulative)})")
        
        # Verify cumulative values: 10, 30, 60, 100, 150
        values = [dp.value for dp in cumulative]
        expected = [10.0, 30.0, 60.0, 100.0, 150.0]
        
        for i, (actual, exp) in enumerate(zip(values, expected)):
            assert_true(
                abs(actual - exp) < 0.01,
                f"Cumulative value {i} is {exp} (got {actual})"
            )
        
        print("[OK] Fluent prefix_op works correctly")
    except Exception as e:
        assert_true(False, f"Fluent prefix_op failed: {e}")
    
    # Test 2: Fluent sliding_window
    try:
        # Window of 2000ms, sum operation
        windowed = fetched.sliding_window(2000, sum)
        assert_true(isinstance(windowed, DatapointSeries), "sliding_window returns DatapointSeries")
        assert_true(len(windowed) > 0, f"Windowed has datapoints (got {len(windowed)})")
        
        print(f"[OK] Fluent sliding_window works correctly (produced {len(windowed)} datapoints)")
    except Exception as e:
        assert_true(False, f"Fluent sliding_window failed: {e}")
    
    # Test 3: Method chaining
    try:
        result = (fetched
            .filter(lambda dp: dp.value >= 20)  # Filter values >= 20
            .map(lambda dp: Datapoint(dp.timestamp, dp.value * 2, dp.dimensions))  # Double values
            .prefix_op(sum))  # Cumulative sum
        
        assert_true(isinstance(result, DatapointSeries), "Method chaining returns DatapointSeries")
        assert_true(len(result) == 4, f"Chained result has 4 datapoints (got {len(result)})")
        
        # After filter: 20, 30, 40, 50
        # After map: 40, 60, 80, 100
        # After prefix_op: 40, 100, 180, 280
        values = [dp.value for dp in result]
        expected = [40.0, 100.0, 180.0, 280.0]
        
        for i, (actual, exp) in enumerate(zip(values, expected)):
            assert_true(
                abs(actual - exp) < 0.01,
                f"Chained value {i} is {exp} (got {actual})"
            )
        
        print("[OK] Method chaining works correctly")
    except Exception as e:
        assert_true(False, f"Method chaining failed: {e}")
    
    # Test 4: Complex chaining with sliding_window
    try:
        complex_result = (fetched
            .filter(lambda dp: dp.value > 10)  # Remove first value
            .sliding_window(2000, sum)  # 2-second rolling sum
            .map(lambda dp: Datapoint(dp.timestamp, dp.value / 2, dp.dimensions)))  # Halve values
        
        assert_true(isinstance(complex_result, DatapointSeries), "Complex chain returns DatapointSeries")
        assert_true(len(complex_result) > 0, f"Complex chain has datapoints (got {len(complex_result)})")
        
        print("[OK] Complex method chaining with sliding_window works")
    except Exception as e:
        assert_true(False, f"Complex chaining failed: {e}")
    
    # Cleanup
    session.delete(f"{base_url}/user")
    
    print("[OK] Fluent API fully functional")


def main():
    print("== Scenario 18: SDK Fluent API ==")
    test_fluent_api()
    print("All checks passed.")


if __name__ == "__main__":
    main()
