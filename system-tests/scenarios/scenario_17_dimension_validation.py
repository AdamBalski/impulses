#!/usr/bin/env python3
"""Scenario 17: Dimension Validation."""
import sys
import time
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
from utils import get_base_url, assert_true, wait_for_health


def test_dimension_validation():
    """Test validation of dimension keys and values."""
    base_url = get_base_url()
    wait_for_health(base_url)
    session = requests.Session()
    
    # Create user and token
    user_email = f"test_dims_{int(time.time())}@example.com"
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
    
    metric_name = f"test_dim_metric_{int(time.time())}"
    
    # Test 1: Empty dimensions object (should be valid)
    resp = requests.post(
        f"{base_url}/data/{metric_name}",
        headers={"X-Data-Token": token_header},
        json=[{
            "timestamp": int(time.time() * 1000),
            "dimensions": {},
            "value": 1.0
        }]
    )
    assert_true(
        resp.status_code == 200,
        f"Empty dimensions object accepted (got {resp.status_code})"
    )
    
    # Test 2: Very long dimension value (e.g., 1000 characters)
    long_value = "x" * 1000
    resp = requests.post(
        f"{base_url}/data/{metric_name}",
        headers={"X-Data-Token": token_header},
        json=[{
            "timestamp": int(time.time() * 1000),
            "dimensions": {"key": long_value},
            "value": 2.0
        }]
    )
    # Implementation may accept or reject very long values
    if resp.status_code == 200:
        print("[OK] Long dimension value (1000 chars) accepted")
    elif resp.status_code == 422:
        print("[OK] Long dimension value rejected with 422")
    else:
        assert_true(False, f"Unexpected status {resp.status_code} for long dimension value")
    
    # Test 3: Many dimensions (10+ keys)
    many_dims = {f"key_{i}": f"value_{i}" for i in range(15)}
    resp = requests.post(
        f"{base_url}/data/{metric_name}",
        headers={"X-Data-Token": token_header},
        json=[{
            "timestamp": int(time.time() * 1000),
            "dimensions": many_dims,
            "value": 3.0
        }]
    )
    assert_true(
        resp.status_code == 200,
        f"Many dimensions (15 keys) accepted (got {resp.status_code})"
    )
    
    # Test 4: Dimension key with valid special characters
    resp = requests.post(
        f"{base_url}/data/{metric_name}",
        headers={"X-Data-Token": token_header},
        json=[{
            "timestamp": int(time.time() * 1000),
            "dimensions": {"valid_key-123": "value"},
            "value": 4.0
        }]
    )
    assert_true(
        resp.status_code == 200,
        f"Dimension key with valid chars accepted (got {resp.status_code})"
    )
    
    # Test 5: Dimension value with special characters (should be allowed)
    resp = requests.post(
        f"{base_url}/data/{metric_name}",
        headers={"X-Data-Token": token_header},
        json=[{
            "timestamp": int(time.time() * 1000),
            "dimensions": {"key": "value with spaces & special!@#"},
            "value": 5.0
        }]
    )
    assert_true(
        resp.status_code == 200,
        f"Dimension value with special chars accepted (got {resp.status_code})"
    )
    
    # Test 6: Dimension value with unicode
    resp = requests.post(
        f"{base_url}/data/{metric_name}",
        headers={"X-Data-Token": token_header},
        json=[{
            "timestamp": int(time.time() * 1000),
            "dimensions": {"key": "unicode_日本語_🎉"},
            "value": 6.0
        }]
    )
    assert_true(
        resp.status_code == 200,
        f"Dimension value with unicode accepted (got {resp.status_code})"
    )
    
    # Test 7: Dimension key that's too long (>100 chars)
    long_key = "k" * 101
    resp = requests.post(
        f"{base_url}/data/{metric_name}",
        headers={"X-Data-Token": token_header},
        json=[{
            "timestamp": int(time.time() * 1000),
            "dimensions": {long_key: "value"},
            "value": 7.0
        }]
    )
    assert_true(
        resp.status_code == 422,
        f"Dimension key >100 chars rejected with 422 (got {resp.status_code})"
    )
    
    # Test 8: Empty dimension key
    resp = requests.post(
        f"{base_url}/data/{metric_name}",
        headers={"X-Data-Token": token_header},
        json=[{
            "timestamp": int(time.time() * 1000),
            "dimensions": {"": "value"},
            "value": 8.0
        }]
    )
    assert_true(
        resp.status_code == 422,
        f"Empty dimension key rejected with 422 (got {resp.status_code})"
    )
    
    # Test 9: Query datapoints and verify dimensions preserved correctly
    resp = requests.get(
        f"{base_url}/data/{metric_name}",
        headers={"X-Data-Token": token_header}
    )
    assert_true(resp.status_code == 200, "Query successful")
    datapoints = resp.json()
    assert_true(len(datapoints) >= 5, f"Multiple datapoints stored (got {len(datapoints)})")
    
    # Verify dimension with special chars preserved
    special_char_dp = [dp for dp in datapoints if "value with spaces" in str(dp.get("dimensions", {}).get("key", ""))]
    assert_true(len(special_char_dp) > 0, "Datapoint with special char dimensions preserved")
    
    # Verify unicode dimension preserved
    unicode_dp = [dp for dp in datapoints if "日本語" in str(dp.get("dimensions", {}).get("key", ""))]
    assert_true(len(unicode_dp) > 0, "Datapoint with unicode dimensions preserved")
    
    print("[OK] Dimension validation working correctly")
    print("[OK] Special characters and unicode supported in dimension values")
    
    # Cleanup
    session.delete(f"{base_url}/user")


def main():
    print("== Scenario 17: Dimension Validation ==")
    test_dimension_validation()
    print("All checks passed.")


if __name__ == "__main__":
    main()
