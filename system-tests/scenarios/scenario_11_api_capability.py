#!/usr/bin/env python3
"""Scenario 11: API vs INGEST Capability."""
import sys
import time
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
from utils import get_base_url, assert_true, wait_for_health


def test_api_capability():
    """Test that API token can read but not write."""
    base_url = get_base_url()
    wait_for_health(base_url)
    session = requests.Session()
    
    # Create user
    user_email = f"test_api_cap_{int(time.time())}@example.com"
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
    
    # Create API token (read-only)
    api_token_name = f"api-token-{int(time.time())}"
    resp = session.post(
        f"{base_url}/token",
        json={"name": api_token_name, "capability": "API", "expires_at": int(time.time()) + 3600}
    )
    assert_true(resp.status_code == 200, "API token created")
    api_token_plaintext = resp.json().get("token_plaintext")
    api_token_header = api_token_plaintext
    
    # Create SUPER token to set up test data
    super_token_name = f"super-token-{int(time.time())}"
    resp = session.post(
        f"{base_url}/token",
        json={"name": super_token_name, "capability": "SUPER", "expires_at": int(time.time()) + 3600}
    )
    assert_true(resp.status_code == 200, "SUPER token created")
    super_token_plaintext = resp.json().get("token_plaintext")
    super_token_header = super_token_plaintext
    
    # Use SUPER token to ingest test data
    metric_name = f"test_api_metric_{int(time.time())}"
    resp = requests.post(
        f"{base_url}/data/{metric_name}",
        headers={"X-Data-Token": super_token_header},
        json=[{
            "timestamp": int(time.time() * 1000),
            "dimensions": {"env": "test"},
            "value": 42.0
        }]
    )
    assert_true(resp.status_code == 200, "SUPER token can write data")
    
    # Test 1: API token can list metrics
    resp = requests.get(
        f"{base_url}/data",
        headers={"X-Data-Token": api_token_header}
    )
    assert_true(
        resp.status_code == 200,
        f"API token can list metrics (got {resp.status_code})"
    )
    metrics = resp.json()
    assert_true(metric_name in metrics, "API token sees ingested metrics")
    
    # Test 2: API token can query datapoints
    resp = requests.get(
        f"{base_url}/data/{metric_name}",
        headers={"X-Data-Token": api_token_header}
    )
    assert_true(
        resp.status_code == 200,
        f"API token can query datapoints (got {resp.status_code})"
    )
    
    # Test 3: API token CANNOT ingest data (write operation)
    resp = requests.post(
        f"{base_url}/data/{metric_name}",
        headers={"X-Data-Token": api_token_header},
        json=[{
            "timestamp": int(time.time() * 1000),
            "dimensions": {"env": "prod"},
            "value": 99.0
        }]
    )
    assert_true(
        resp.status_code == 403,
        f"API token cannot write data, rejected with 403 (got {resp.status_code})"
    )
    
    # Test 4: API token CANNOT delete metrics (write operation)
    resp = requests.delete(
        f"{base_url}/data/{metric_name}",
        headers={"X-Data-Token": api_token_header}
    )
    assert_true(
        resp.status_code == 403,
        f"API token cannot delete metrics, rejected with 403 (got {resp.status_code})"
    )
    
    # Verify clear separation: API = read-only, INGEST = write-only, SUPER = both
    print("[OK] API capability provides read-only access")
    print("[OK] Write operations properly rejected for API tokens")
    
    # Cleanup
    session.delete(f"{base_url}/user")


def main():
    print("== Scenario 11: API vs INGEST Capability ==")
    test_api_capability()
    print("All checks passed.")


if __name__ == "__main__":
    main()
