#!/usr/bin/env python3
"""Scenario 8: Invalid Metric Names."""
import sys
import time
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
from utils import get_base_url, assert_true, wait_for_health


def test_invalid_metric_names():
    """Test validation of metric names."""
    base_url = get_base_url()
    wait_for_health(base_url)
    session = requests.Session()
    
    # Create user and token
    user_email = f"test_metrics_{int(time.time())}@example.com"
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
    
    token_name = f"test-token-{int(time.time())}"
    resp = session.post(
        f"{base_url}/token",
        json={"name": token_name, "capability": "SUPER", "expires_at": int(time.time()) + 3600}
    )
    assert_true(resp.status_code == 200, "Token created")
    token_plaintext = resp.json().get("token_plaintext")
    token_header = token_plaintext
    
    sample_datapoint = [{"timestamp": int(time.time() * 1000), "dimensions": {}, "value": 1.0}]
    
    # Test 1: Reserved prefix "imp." should be rejected
    resp = requests.post(
        f"{base_url}/data/imp.reserved_metric",
        headers={"X-Data-Token": token_header},
        json=sample_datapoint
    )
    assert_true(
        resp.status_code == 403,
        f"Metric name starting with 'imp.' rejected with 403 (got {resp.status_code})"
    )
    
    # Test 2: Empty metric name should be rejected
    resp = requests.post(
        f"{base_url}/data/",
        headers={"X-Data-Token": token_header},
        json=sample_datapoint
    )
    # This might be 404 or 405 due to routing, not reaching validation
    assert_true(
        resp.status_code in [404, 405, 422],
        f"Empty metric name rejected (got {resp.status_code})"
    )
    
    # Test 3: Metric name with invalid characters (e.g., spaces)
    resp = requests.post(
        f"{base_url}/data/invalid metric name",
        headers={"X-Data-Token": token_header},
        json=sample_datapoint
    )
    # URL encoding might make this work differently, but invalid chars should fail
    assert_true(
        resp.status_code == 422,
        f"Metric name with spaces rejected with 422 (got {resp.status_code})"
    )
    
    # Test 4: Metric name that's too long (>100 characters)
    long_metric_name = "a" * 101
    resp = requests.post(
        f"{base_url}/data/{long_metric_name}",
        headers={"X-Data-Token": token_header},
        json=sample_datapoint
    )
    assert_true(
        resp.status_code == 422,
        f"Metric name >100 chars rejected with 422 (got {resp.status_code})"
    )
    
    # Test 5: Valid edge case - exactly 99 characters (should succeed)
    valid_long_name = "a" * 99
    resp = requests.post(
        f"{base_url}/data/{valid_long_name}",
        headers={"X-Data-Token": token_header},
        json=sample_datapoint
    )
    assert_true(
        resp.status_code == 200,
        f"Valid metric name (99 chars) accepted (got {resp.status_code})"
    )
    
    # Test 6: Valid metric name with allowed special characters
    valid_metric = "test_metric.name-123:value"
    resp = requests.post(
        f"{base_url}/data/{valid_metric}",
        headers={"X-Data-Token": token_header},
        json=sample_datapoint
    )
    assert_true(
        resp.status_code == 200,
        f"Valid metric with special chars accepted (got {resp.status_code})"
    )
    
    # Cleanup
    session.delete(f"{base_url}/user")


def main():
    print("== Scenario 8: Invalid Metric Names ==")
    test_invalid_metric_names()
    print("All checks passed.")


if __name__ == "__main__":
    main()
