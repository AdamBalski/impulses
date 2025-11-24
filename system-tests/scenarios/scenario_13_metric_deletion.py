#!/usr/bin/env python3
"""Scenario 13: Metric Deletion."""
import sys
import time
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
from utils import get_base_url, assert_true, wait_for_health


def test_metric_deletion():
    """Test metric deletion removes data and metric from list."""
    base_url = get_base_url()
    wait_for_health(base_url)
    session = requests.Session()
    
    # Create user and token
    user_email = f"test_delete_{int(time.time())}@example.com"
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
    
    # Ingest data for metric
    metric_name = f"metric_to_delete_{int(time.time())}"
    resp = requests.post(
        f"{base_url}/data/{metric_name}",
        headers={"X-Data-Token": token_header},
        json=[
            {
                "timestamp": int(time.time() * 1000),
                "dimensions": {"env": "test"},
                "value": 42.0
            },
            {
                "timestamp": int(time.time() * 1000) + 1000,
                "dimensions": {"env": "prod"},
                "value": 99.0
            }
        ]
    )
    assert_true(resp.status_code == 200, "Data ingested successfully")
    
    # Verify metric exists in list
    resp = requests.get(
        f"{base_url}/data",
        headers={"X-Data-Token": token_header}
    )
    assert_true(resp.status_code == 200, "Metric list retrieved")
    metrics = resp.json()
    assert_true(metric_name in metrics, f"Metric '{metric_name}' appears in list before deletion")
    
    # Query metric to verify data exists
    resp = requests.get(
        f"{base_url}/data/{metric_name}",
        headers={"X-Data-Token": token_header}
    )
    assert_true(resp.status_code == 200, "Metric data retrieved")
    datapoints = resp.json()
    assert_true(len(datapoints) == 2, f"2 datapoints exist before deletion (got {len(datapoints)})")
    
    # Delete the metric
    resp = requests.delete(
        f"{base_url}/data/{metric_name}",
        headers={"X-Data-Token": token_header}
    )
    assert_true(resp.status_code == 200, f"Metric deleted successfully (got {resp.status_code})")
    
    # Verify metric no longer appears in list
    resp = requests.get(
        f"{base_url}/data",
        headers={"X-Data-Token": token_header}
    )
    assert_true(resp.status_code == 200, "Metric list retrieved after deletion")
    metrics_after = resp.json()
    assert_true(
        metric_name not in metrics_after,
        f"Metric '{metric_name}' removed from list after deletion"
    )
    
    # Query deleted metric should return 200 OK with empty datapoints
    resp = requests.get(
        f"{base_url}/data/{metric_name}",
        headers={"X-Data-Token": token_header}
    )
    assert_true(resp.status_code == 200, f"Deleted metric query returned 200 (got {resp.status_code})")
    datapoints_after = resp.json()
    assert_true(
        len(datapoints_after) == 0,
        "Query returns empty datapoints after metric deletion"
    )
    
    # Cleanup
    session.delete(f"{base_url}/user")


def main():
    print("== Scenario 13: Metric Deletion ==")
    test_metric_deletion()
    print("All checks passed.")


if __name__ == "__main__":
    main()
