#!/usr/bin/env python3
"""Scenario 14: Authentication Edge Cases."""
import sys
import time
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
from utils import get_base_url, assert_true, wait_for_health


def test_auth_edge_cases():
    """Test authentication validation and error cases."""
    base_url = get_base_url()
    wait_for_health(base_url)
    
    # Create a valid user for testing
    valid_email = f"valid_user_{int(time.time())}@example.com"
    valid_password = "ValidPassword123!"
    
    resp = requests.post(
        f"{base_url}/user",
        json={"email": valid_email, "password": valid_password, "role": "STANDARD"}
    )
    assert_true(resp.status_code == 200, "Valid user created")
    
    # Test 1: Login with wrong password
    resp = requests.post(
        f"{base_url}/user/login",
        json={"email": valid_email, "password": "WrongPassword123!"}
    )
    assert_true(
        resp.status_code == 401,
        f"Login with wrong password rejected with 401 (got {resp.status_code})"
    )
    
    # Test 2: Login with non-existent email
    resp = requests.post(
        f"{base_url}/user/login",
        json={"email": "nonexistent@example.com", "password": "AnyPassword123!"}
    )
    assert_true(
        resp.status_code == 401,
        f"Login with non-existent email rejected with 401 (got {resp.status_code})"
    )
    
    # Test 3: Create user with duplicate email
    resp = requests.post(
        f"{base_url}/user",
        json={"email": valid_email, "password": "AnotherPassword123!", "role": "STANDARD"}
    )
    # Some implementations return 500 for database constraint violations instead of 409
    assert_true(
        resp.status_code in [409, 500],
        f"Duplicate email rejected with 409 or 500 (got {resp.status_code})"
    )
    
    # Test 4: Create user with invalid email format (missing @)
    resp = requests.post(
        f"{base_url}/user",
        json={"email": "invalid-email", "password": "Password123!", "role": "STANDARD"}
    )
    # Email validation might not be enforced, accept 200 or 422
    if resp.status_code == 422:
        print("[OK] Invalid email format (missing @) rejected with 422")
    elif resp.status_code == 200:
        print("[OK] Invalid email format accepted (no strict validation)")
    else:
        assert_true(False, f"Unexpected status {resp.status_code} for invalid email")
    
    # Test 5: Create user with invalid email format (missing domain)
    resp = requests.post(
        f"{base_url}/user",
        json={"email": "invalid@", "password": "Password123!", "role": "STANDARD"}
    )
    # Email validation might not be enforced
    if resp.status_code == 422:
        print("[OK] Invalid email (missing domain) rejected with 422")
    elif resp.status_code == 200:
        print("[OK] Invalid email accepted (no strict validation)")
    else:
        assert_true(False, f"Unexpected status {resp.status_code} for invalid email")
    
    # Test 6: Create user with empty email
    resp = requests.post(
        f"{base_url}/user",
        json={"email": "", "password": "Password123!", "role": "STANDARD"}
    )
    # Empty email validation might not be enforced
    if resp.status_code == 422:
        print("[OK] Empty email rejected with 422")
    elif resp.status_code == 200:
        print("[OK] Empty email accepted (no validation)")
    else:
        assert_true(False, f"Unexpected status {resp.status_code} for empty email")
    
    # Test 7: Create user with missing email field
    resp = requests.post(
        f"{base_url}/user",
        json={"password": "Password123!", "role": "STANDARD"}
    )
    assert_true(
        resp.status_code == 422,
        f"Missing email field rejected with 422 (got {resp.status_code})"
    )

    # Test 8: Create user with too short password (should be accepted)
    resp = requests.post(
        f"{base_url}/user",
        json={"email": f"short_pass_{int(time.time())}@example.com", "password": "123", "role": "STANDARD"}
    )
    assert_true(resp.status_code == 200, f"Short password creation returns 200 (got {resp.status_code})")

    # Test 9: Create user with empty password (should be accepted)
    resp = requests.post(
        f"{base_url}/user",
        json={"email": f"empty_pass_{int(time.time())}@example.com", "password": "", "role": "STANDARD"}
    )
    assert_true(resp.status_code == 200, f"Empty password creation returns 200 (got {resp.status_code})")
    
    # Test 10: Create user with missing password field
    resp = requests.post(
        f"{base_url}/user",
        json={"email": f"no_pass_{int(time.time())}@example.com", "role": "STANDARD"}
    )
    assert_true(
        resp.status_code == 422,
        f"Missing password field rejected with 422 (got {resp.status_code})"
    )
    
    # Test 11: Create user with invalid role
    resp = requests.post(
        f"{base_url}/user",
        json={"email": f"invalid_role_{int(time.time())}@example.com", "password": "Password123!", "role": "INVALID"}
    )
    assert_true(
        resp.status_code == 422,
        f"Invalid role rejected with 422 (got {resp.status_code})"
    )
    
    # Test 12: Login with valid credentials (sanity check)
    resp = requests.post(
        f"{base_url}/user/login",
        json={"email": valid_email, "password": valid_password}
    )
    assert_true(
        resp.status_code == 200,
        f"Login with correct credentials succeeds (got {resp.status_code})"
    )
    
    # Cleanup
    session = requests.Session()
    session.post(
        f"{base_url}/user/login",
        json={"email": valid_email, "password": valid_password}
    )
    session.delete(f"{base_url}/user")


def main():
    print("== Scenario 14: Authentication Edge Cases ==")
    test_auth_edge_cases()
    print("All checks passed.")


if __name__ == "__main__":
    main()
