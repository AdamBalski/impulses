#!/usr/bin/env python3
"""Scenario 7: Multi-User Data Isolation."""
import sys
import time
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
from utils import get_base_url, assert_true, wait_for_health


def test_multi_user_isolation():
    """Test that users can only access their own data."""
    base_url = get_base_url()
    wait_for_health(base_url)
    
    # Create User A
    user_a_session = requests.Session()
    user_a_email = f"user_a_{int(time.time())}@example.com"
    user_a_password = "PasswordA123!"
    
    resp = user_a_session.post(
        f"{base_url}/user",
        json={"email": user_a_email, "password": user_a_password, "role": "STANDARD"}
    )
    assert_true(resp.status_code == 200, "User A created")
    
    resp = user_a_session.post(
        f"{base_url}/user/login",
        json={"email": user_a_email, "password": user_a_password}
    )
    assert_true(resp.status_code == 200, "User A logged in")
    
    # Create token for User A
    token_a_name = f"token-a-{int(time.time())}"
    resp = user_a_session.post(
        f"{base_url}/token",
        json={"name": token_a_name, "capability": "SUPER", "expires_at": int(time.time()) + 3600}
    )
    assert_true(resp.status_code == 200, "Token A created")
    token_a_plaintext = resp.json().get("token_plaintext")
    token_a_header = token_a_plaintext
    
    # Create User B
    user_b_session = requests.Session()
    user_b_email = f"user_b_{int(time.time())}@example.com"
    user_b_password = "PasswordB123!"
    
    resp = user_b_session.post(
        f"{base_url}/user",
        json={"email": user_b_email, "password": user_b_password, "role": "STANDARD"}
    )
    assert_true(resp.status_code == 200, "User B created")
    
    resp = user_b_session.post(
        f"{base_url}/user/login",
        json={"email": user_b_email, "password": user_b_password}
    )
    assert_true(resp.status_code == 200, "User B logged in")
    
    # Create token for User B
    token_b_name = f"token-b-{int(time.time())}"
    resp = user_b_session.post(
        f"{base_url}/token",
        json={"name": token_b_name, "capability": "SUPER", "expires_at": int(time.time()) + 3600}
    )
    assert_true(resp.status_code == 200, "Token B created")
    token_b_plaintext = resp.json().get("token_plaintext")
    token_b_header = token_b_plaintext
    
    # Both users ingest data to same metric name
    shared_metric_name = "shared_metric_name"
    
    resp = requests.post(
        f"{base_url}/data/{shared_metric_name}",
        headers={"X-Data-Token": token_a_header},
        json=[{"timestamp": int(time.time() * 1000), "dimensions": {"user": "A"}, "value": 100.0}]
    )
    assert_true(resp.status_code == 200, "User A ingested data")
    
    resp = requests.post(
        f"{base_url}/data/{shared_metric_name}",
        headers={"X-Data-Token": token_b_header},
        json=[{"timestamp": int(time.time() * 1000), "dimensions": {"user": "B"}, "value": 200.0}]
    )
    assert_true(resp.status_code == 200, "User B ingested data")
    
    # User A queries and sees only their data
    resp = requests.get(
        f"{base_url}/data/{shared_metric_name}",
        headers={"X-Data-Token": token_a_header}
    )
    assert_true(resp.status_code == 200, "User A can query their data")
    datapoints_a = resp.json()
    assert_true(len(datapoints_a) == 1, f"User A sees exactly 1 datapoint (got {len(datapoints_a)})")
    assert_true(datapoints_a[0]["value"] == 100.0, "User A sees their own value (100.0)")
    assert_true(datapoints_a[0]["dimensions"]["user"] == "A", "User A sees their own dimension")
    
    # User B queries and sees only their data
    resp = requests.get(
        f"{base_url}/data/{shared_metric_name}",
        headers={"X-Data-Token": token_b_header}
    )
    assert_true(resp.status_code == 200, "User B can query their data")
    datapoints_b = resp.json()
    assert_true(len(datapoints_b) == 1, f"User B sees exactly 1 datapoint (got {len(datapoints_b)})")
    assert_true(datapoints_b[0]["value"] == 200.0, "User B sees their own value (200.0)")
    assert_true(datapoints_b[0]["dimensions"]["user"] == "B", "User B sees their own dimension")
    
    # User A tries to use User B's token (cross-user access) - should fail
    resp = requests.get(
        f"{base_url}/data/{shared_metric_name}",
        headers={"X-Data-Token": token_b_header}
    )
    # This should succeed but return User B's data, not User A's
    # The token auth is valid, it just returns different user's data
    # So we verify the isolation by checking the data content
    datapoints_cross = resp.json()
    assert_true(len(datapoints_cross) == 1, "Cross-token access returns data")
    assert_true(datapoints_cross[0]["value"] == 200.0, "Cross-token access sees User B's data, not User A's")
    
    # Cleanup
    user_a_session.delete(f"{base_url}/user")
    user_b_session.delete(f"{base_url}/user")


def main():
    print("== Scenario 7: Multi-User Data Isolation ==")
    test_multi_user_isolation()
    print("All checks passed.")


if __name__ == "__main__":
    main()
