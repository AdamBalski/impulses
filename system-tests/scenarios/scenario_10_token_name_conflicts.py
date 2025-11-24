#!/usr/bin/env python3
"""Scenario 10: Token Name Conflicts."""
import sys
import time
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
from utils import get_base_url, assert_true, wait_for_health


def test_token_name_conflicts():
    """Test token name uniqueness constraints."""
    base_url = get_base_url()
    wait_for_health(base_url)
    
    # Create User A
    user_a_session = requests.Session()
    user_a_email = f"user_token_a_{int(time.time())}@example.com"
    resp = user_a_session.post(
        f"{base_url}/user",
        json={"email": user_a_email, "password": "PasswordA123!", "role": "STANDARD"}
    )
    assert_true(resp.status_code == 200, "User A created")
    
    resp = user_a_session.post(
        f"{base_url}/user/login",
        json={"email": user_a_email, "password": "PasswordA123!"}
    )
    assert_true(resp.status_code == 200, "User A logged in")
    
    # Create first token for User A
    token_name = "my-token"
    resp = user_a_session.post(
        f"{base_url}/token",
        json={"name": token_name, "capability": "SUPER", "expires_at": int(time.time()) + 3600}
    )
    assert_true(resp.status_code == 200, "First token created for User A")
    
    # Attempt to create second token with same name for User A
    resp = user_a_session.post(
        f"{base_url}/token",
        json={"name": token_name, "capability": "API", "expires_at": int(time.time()) + 3600}
    )
    # Duplicate token names for the same user are allowed - must return 200
    assert_true(resp.status_code == 200, f"Duplicate token name must be allowed (got {resp.status_code})")
    
    # Create User B
    user_b_session = requests.Session()
    user_b_email = f"user_token_b_{int(time.time())}@example.com"
    resp = user_b_session.post(
        f"{base_url}/user",
        json={"email": user_b_email, "password": "PasswordB123!", "role": "STANDARD"}
    )
    assert_true(resp.status_code == 200, "User B created")
    
    resp = user_b_session.post(
        f"{base_url}/user/login",
        json={"email": user_b_email, "password": "PasswordB123!"}
    )
    assert_true(resp.status_code == 200, "User B logged in")
    
    # User B creates token with same name as User A's token
    resp = user_b_session.post(
        f"{base_url}/token",
        json={"name": token_name, "capability": "INGEST", "expires_at": int(time.time()) + 3600}
    )
    assert_true(
        resp.status_code == 200,
        f"Different users can have tokens with same name (got {resp.status_code})"
    )
    
    # List tokens for User A
    resp = user_a_session.get(f"{base_url}/token")
    assert_true(resp.status_code == 200, "User A can list tokens")
    tokens_a = resp.json()
    assert_true(isinstance(tokens_a, list), "Token list is array")
    # Should see at least 1 token (possibly 2 if duplicates allowed)
    assert_true(len(tokens_a) >= 1, f"User A has at least 1 token (got {len(tokens_a)})")
    
    # List tokens for User B
    resp = user_b_session.get(f"{base_url}/token")
    assert_true(resp.status_code == 200, "User B can list tokens")
    tokens_b = resp.json()
    assert_true(len(tokens_b) == 1, f"User B has exactly 1 token (got {len(tokens_b)})")
    
    # Verify User A doesn't see User B's token
    token_ids_a = [t["id"] for t in tokens_a]
    token_ids_b = [t["id"] for t in tokens_b]
    common_ids = set(token_ids_a) & set(token_ids_b)
    assert_true(len(common_ids) == 0, "Users don't see each other's tokens")
    
    # Cleanup
    user_a_session.delete(f"{base_url}/user")
    user_b_session.delete(f"{base_url}/user")


def main():
    print("== Scenario 10: Token Name Conflicts ==")
    test_token_name_conflicts()
    print("All checks passed.")


if __name__ == "__main__":
    main()
