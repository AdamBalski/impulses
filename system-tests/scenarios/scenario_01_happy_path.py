#!/usr/bin/env python3
"""Scenario 1: Happy path - Complete user lifecycle and data ingestion."""
import sys
import time
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
from utils import get_base_url, assert_true, wait_for_health


def test_happy_path():
    """Test complete user lifecycle with data ingestion."""
    base_url = get_base_url()
    wait_for_health(base_url)
    session = requests.Session()
    
    # Step 1: Create user
    user_email = f"test_{int(time.time())}@example.com"
    user_password = "SecurePassword123!"
    
    resp = session.post(
        f"{base_url}/user",
        json={
            "email": user_email,
            "password": user_password,
            "role": "STANDARD"
        }
    )
    assert_true(resp.status_code == 200, f"Create user returned 200 (got {resp.status_code})")
    user_data = resp.json()
    user_id = user_data.get("id")
    assert_true(user_id is not None, "User ID present in response")
    
    # Step 2: Login
    resp = session.post(
        f"{base_url}/user/login",
        json={
            "email": user_email,
            "password": user_password
        }
    )
    assert_true(resp.status_code == 200, f"Login returned 200 (got {resp.status_code})")
    assert_true("sid" in session.cookies, "Session cookie set after login")
    
    # Step 3: Create token with SUPER capability
    token_name = f"test-token-{int(time.time())}"
    resp = session.post(
        f"{base_url}/token",
        json={
            "name": token_name,
            "capability": "SUPER",
            "expires_at": int(time.time()) + 3600
        }
    )
    assert_true(resp.status_code == 200, f"Create token returned 200 (got {resp.status_code})")
    token_data = resp.json()
    token_plaintext = token_data.get("token_plaintext")
    token_id = token_data.get("id")
    assert_true(token_plaintext is not None, "Token plaintext returned on creation")
    
    # Construct X-Data-Token header
    data_token_header = token_plaintext
    
    # Step 4: Ingest datapoints
    metric_name = "test_metric_counter"
    timestamp = int(time.time() * 1000)
    
    datapoints = [
        {
            "timestamp": timestamp,
            "dimensions": {"env": "test", "region": "us-west"},
            "value": 42.0
        },
        {
            "timestamp": timestamp + 1000,
            "dimensions": {"env": "test", "region": "us-east"},
            "value": 100.5
        }
    ]
    
    resp = requests.post(
        f"{base_url}/data/{metric_name}",
        headers={"X-Data-Token": data_token_header},
        json=datapoints
    )
    assert_true(resp.status_code == 200, f"Ingest datapoints returned 200 (got {resp.status_code})")
    
    # Step 5: List metrics
    resp = requests.get(
        f"{base_url}/data",
        headers={"X-Data-Token": data_token_header}
    )
    assert_true(resp.status_code == 200, f"List metrics returned 200 (got {resp.status_code})")
    metrics = resp.json()
    assert_true(isinstance(metrics, list), "Metrics response is a list")
    assert_true(metric_name in metrics, f"Ingested metric '{metric_name}' appears in metrics list")
    
    # Step 6: Query datapoints
    resp = requests.get(
        f"{base_url}/data/{metric_name}",
        headers={"X-Data-Token": data_token_header}
    )
    assert_true(resp.status_code == 200, f"Query datapoints returned 200 (got {resp.status_code})")
    datapoints_result = resp.json()
    assert_true(len(datapoints_result) >= 2, f"Query returned at least 2 datapoints (got {len(datapoints_result)})")
    
    # Verify ingested data
    values = [dp["value"] for dp in datapoints_result]
    assert_true(42.0 in values, "First ingested value (42.0) present in query results")
    assert_true(100.5 in values, "Second ingested value (100.5) present in query results")
    
    # Step 7: Delete token
    resp = session.delete(
        f"{base_url}/token/{token_id}"
    )
    assert_true(resp.status_code == 200, f"Delete token returned 200 (got {resp.status_code})")
    
    # Verify token no longer works
    resp = requests.get(
        f"{base_url}/data",
        headers={"X-Data-Token": data_token_header}
    )
    assert_true(resp.status_code == 401, f"Deleted token rejected with 401 (got {resp.status_code})")
    
    # Step 8: Delete user
    resp = session.delete(f"{base_url}/user")
    assert_true(resp.status_code == 200, f"Delete user returned 200 (got {resp.status_code})")
    
    # Verify user can no longer login
    resp = session.post(
        f"{base_url}/user/login",
        json={
            "email": user_email,
            "password": user_password
        }
    )
    assert_true(resp.status_code == 401, f"Deleted user login rejected with 401 (got {resp.status_code})")


def main():
    print("== Scenario 1: Happy path - User lifecycle and data ingestion ==")
    test_happy_path()
    print("All checks passed.")


if __name__ == "__main__":
    main()
