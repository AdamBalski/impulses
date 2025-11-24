#!/usr/bin/env python3
"""Scenario 5: Token deletion."""
import sys
import time
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
from utils import get_base_url, assert_true, wait_for_health


def test_token_deletion():
    """Test that deleted tokens cannot be used."""
    base_url = get_base_url()
    wait_for_health(base_url)
    session = requests.Session()
    
    # Step 1: Create user
    user_email = f"test_delete_{int(time.time())}@example.com"
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
    
    # Step 2: Login
    resp = session.post(
        f"{base_url}/user/login",
        json={
            "email": user_email,
            "password": user_password
        }
    )
    assert_true(resp.status_code == 200, f"Login returned 200 (got {resp.status_code})")
    
    # Step 3: Create token
    token_name = f"delete-token-{int(time.time())}"
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
    assert_true(token_plaintext is not None, "Token plaintext returned")
    assert_true(token_id is not None, "Token id returned")
    
    data_token_header = token_plaintext
    
    # Step 4: Use token to ingest data (verify it works)
    metric_name = f"test_delete_metric_{int(time.time())}"
    resp = requests.post(
        f"{base_url}/data/{metric_name}",
        headers={"X-Data-Token": data_token_header},
        json=[
            {
                "timestamp": int(time.time() * 1000),
                "dimensions": {"test": "before_delete"},
                "value": 99.0
            }
        ]
    )
    assert_true(
        resp.status_code == 200,
        f"Token works before deletion (got {resp.status_code})"
    )
    
    # Step 5: Delete the token
    resp = session.delete(
        f"{base_url}/token/{token_id}"
    )
    assert_true(resp.status_code == 200, f"Token deleted successfully (got {resp.status_code})")
    
    # Step 6: Attempt to use deleted token (should fail with 401)
    resp = requests.post(
        f"{base_url}/data/{metric_name}",
        headers={"X-Data-Token": data_token_header},
        json=[
            {
                "timestamp": int(time.time() * 1000),
                "dimensions": {"test": "after_delete"},
                "value": 100.0
            }
        ]
    )
    assert_true(
        resp.status_code == 401,
        f"Deleted token rejected with 401 (got {resp.status_code})"
    )
    
    # Step 7: Also test read operations with deleted token
    resp = requests.get(
        f"{base_url}/data",
        headers={"X-Data-Token": data_token_header}
    )
    assert_true(
        resp.status_code == 401,
        f"Deleted token rejected for read with 401 (got {resp.status_code})"
    )
    
    # Cleanup
    session.delete(f"{base_url}/user")


def main():
    print("== Scenario 5: Token deletion ==")
    test_token_deletion()
    print("All checks passed.")


if __name__ == "__main__":
    main()
