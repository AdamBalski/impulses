#!/usr/bin/env python3
"""Scenario 9: Invalid Data Payloads."""
import sys
import time
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
from utils import get_base_url, assert_true, wait_for_health


def test_invalid_payloads():
    """Test validation of datapoint payloads."""
    base_url = get_base_url()
    wait_for_health(base_url)
    session = requests.Session()
    
    # Create user and token
    user_email = f"test_payloads_{int(time.time())}@example.com"
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
    
    metric_name = f"test_payload_metric_{int(time.time())}"
    
    # Test 1: Invalid dimension key with spaces
    resp = requests.post(
        f"{base_url}/data/{metric_name}",
        headers={"X-Data-Token": token_header},
        json=[{
            "timestamp": int(time.time() * 1000),
            "dimensions": {"invalid key": "value"},
            "value": 1.0
        }]
    )
    assert_true(
        resp.status_code == 422,
        f"Dimension key with spaces rejected with 422 (got {resp.status_code})"
    )
    
    # Test 2: Dimension key with special characters (might be allowed)
    resp = requests.post(
        f"{base_url}/data/{metric_name}",
        headers={"X-Data-Token": token_header},
        json=[{
            "timestamp": int(time.time() * 1000),
            "dimensions": {"key@symbol": "value"},
            "value": 1.0
        }]
    )
    # @ might be allowed in dimension keys, so accept either 200 or 422
    if resp.status_code == 200:
        print("[OK] Dimension key with @ accepted")
    elif resp.status_code == 422:
        print("[OK] Dimension key with @ rejected with 422")
    else:
        assert_true(False, f"Unexpected status {resp.status_code} for dimension key with @")
    
    # Test 3: Empty datapoints array (might be valid or invalid depending on implementation)
    resp = requests.post(
        f"{base_url}/data/{metric_name}",
        headers={"X-Data-Token": token_header},
        json=[]
    )
    # Empty array might be accepted (idempotent) or rejected
    assert_true(
        resp.status_code in [200, 422],
        f"Empty datapoints array handled (got {resp.status_code})"
    )
    
    # Test 4: Timestamp as string instead of int
    resp = requests.post(
        f"{base_url}/data/{metric_name}",
        headers={"X-Data-Token": token_header},
        json=[{
            "timestamp": "not-a-number",
            "dimensions": {},
            "value": 1.0
        }]
    )
    assert_true(
        resp.status_code == 422,
        f"String timestamp rejected with 422 (got {resp.status_code})"
    )
    
    # Test 5: Value as string instead of float
    resp = requests.post(
        f"{base_url}/data/{metric_name}",
        headers={"X-Data-Token": token_header},
        json=[{
            "timestamp": int(time.time() * 1000),
            "dimensions": {},
            "value": "not-a-number"
        }]
    )
    assert_true(
        resp.status_code == 422,
        f"String value rejected with 422 (got {resp.status_code})"
    )
    
    # Test 6: Null value
    resp = requests.post(
        f"{base_url}/data/{metric_name}",
        headers={"X-Data-Token": token_header},
        json=[{
            "timestamp": int(time.time() * 1000),
            "dimensions": {},
            "value": None
        }]
    )
    assert_true(
        resp.status_code == 422,
        f"Null value rejected with 422 (got {resp.status_code})"
    )
    
    # Test 7: Missing required field (timestamp)
    resp = requests.post(
        f"{base_url}/data/{metric_name}",
        headers={"X-Data-Token": token_header},
        json=[{
            "dimensions": {},
            "value": 1.0
        }]
    )
    assert_true(
        resp.status_code == 422,
        f"Missing timestamp rejected with 422 (got {resp.status_code})"
    )
    
    # Test 8: Missing required field (value)
    resp = requests.post(
        f"{base_url}/data/{metric_name}",
        headers={"X-Data-Token": token_header},
        json=[{
            "timestamp": int(time.time() * 1000),
            "dimensions": {}
        }]
    )
    assert_true(
        resp.status_code == 422,
        f"Missing value rejected with 422 (got {resp.status_code})"
    )
    
    # Test 9: Missing required field (dimensions)
    resp = requests.post(
        f"{base_url}/data/{metric_name}",
        headers={"X-Data-Token": token_header},
        json=[{
            "timestamp": int(time.time() * 1000),
            "value": 1.0
        }]
    )
    assert_true(
        resp.status_code == 422,
        f"Missing dimensions rejected with 422 (got {resp.status_code})"
    )
    
    # Test 10: Valid payload (sanity check)
    resp = requests.post(
        f"{base_url}/data/{metric_name}",
        headers={"X-Data-Token": token_header},
        json=[{
            "timestamp": int(time.time() * 1000),
            "dimensions": {"env": "test"},
            "value": 42.0
        }]
    )
    assert_true(
        resp.status_code == 200,
        f"Valid payload accepted (got {resp.status_code})"
    )
    
    # Cleanup
    session.delete(f"{base_url}/user")


def main():
    print("== Scenario 9: Invalid Data Payloads ==")
    test_invalid_payloads()
    print("All checks passed.")


if __name__ == "__main__":
    main()
