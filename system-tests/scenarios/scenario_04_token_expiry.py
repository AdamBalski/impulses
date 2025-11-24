#!/usr/bin/env python3
"""Scenario 4: Token expiry."""
import sys
import time
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
from utils import get_base_url, assert_true, wait_for_health


def test_token_expiry():
    """Test that expired tokens are rejected."""
    base_url = get_base_url()
    wait_for_health(base_url)
    session = requests.Session()
    
    # Step 1: Create user
    user_email = f"test_expiry_{int(time.time())}@example.com"
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
    
    # Step 3: Create token with very short TTL (expires in 2 seconds)
    token_name = f"expiry-token-{int(time.time())}"
    expires_at = int(time.time()) + 2  # Expires in 2 seconds
    
    resp = session.post(
        f"{base_url}/token",
        json={
            "name": token_name,
            "capability": "SUPER",
            "expires_at": expires_at
        }
    )
    assert_true(resp.status_code == 200, f"Create token with short TTL returned 200 (got {resp.status_code})")
    token_plaintext = resp.json().get("token_plaintext")
    assert_true(token_plaintext is not None, "Token plaintext returned")
    
    data_token_header = token_plaintext
    
    # Step 4: Verify token works before expiry
    resp = requests.get(
        f"{base_url}/data",
        headers={"X-Data-Token": data_token_header}
    )
    assert_true(
        resp.status_code == 200,
        f"Token works before expiry (got {resp.status_code})"
    )
    
    # Step 5: Wait for token to expire (wait 3 seconds)
    print("[INFO] Waiting 3 seconds for token to expire...")
    time.sleep(3)
    
    # Step 6: Attempt to use expired token (should fail with 401)
    resp = requests.get(
        f"{base_url}/data",
        headers={"X-Data-Token": data_token_header}
    )
    assert_true(
        resp.status_code == 401,
        f"Expired token rejected with 401 (got {resp.status_code})"
    )
    
    # Cleanup (token already expired, just delete user)
    session.delete(f"{base_url}/user")


def main():
    print("== Scenario 4: Token expiry ==")
    test_token_expiry()
    print("All checks passed.")


if __name__ == "__main__":
    main()
