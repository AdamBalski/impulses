#!/usr/bin/env python3
"""Scenario 12: Session Management."""
import sys
import time
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
from utils import get_base_url, assert_true, wait_for_health


def test_session_management():
    """Test login, logout, and session invalidation."""
    base_url = get_base_url()
    wait_for_health(base_url)
    
    # Create user
    user_email = f"test_session_{int(time.time())}@example.com"
    user_password = "Password123!"
    
    resp = requests.post(
        f"{base_url}/user",
        json={"email": user_email, "password": user_password, "role": "STANDARD"}
    )
    assert_true(resp.status_code == 200, "User created")
    
    # Test 1: Login and get session cookie
    session1 = requests.Session()
    resp = session1.post(
        f"{base_url}/user/login",
        json={"email": user_email, "password": user_password}
    )
    assert_true(resp.status_code == 200, f"Login successful (got {resp.status_code})")
    assert_true("sid" in session1.cookies, "Session cookie (sid) set after login")
    
    # Test 2: Use session to access protected endpoint (list tokens)
    resp = session1.get(f"{base_url}/token")
    assert_true(
        resp.status_code == 200,
        f"Session can access protected endpoint (got {resp.status_code})"
    )
    
    # Test 3: Create token using session
    token_name = f"session-token-{int(time.time())}"
    resp = session1.post(
        f"{base_url}/token",
        json={"name": token_name, "capability": "SUPER", "expires_at": int(time.time()) + 3600}
    )
    assert_true(resp.status_code == 200, "Session can create token")
    
    # Test 4: Logout
    resp = session1.post(f"{base_url}/user/logout")
    assert_true(resp.status_code == 200, f"Logout returned 200 (got {resp.status_code})")
    
    # Test 5: After logout, session should be invalidated
    resp = session1.get(f"{base_url}/token")
    assert_true(
        resp.status_code == 401,
        f"Logged out session rejected with 401 (got {resp.status_code})"
    )
    
    # Test 6: Attempt to access protected endpoint with old session cookie
    resp = session1.post(
        f"{base_url}/token",
        json={"name": "should-fail", "capability": "API", "expires_at": int(time.time()) + 3600}
    )
    assert_true(
        resp.status_code == 401,
        f"Old session cookie rejected with 401 (got {resp.status_code})"
    )
    
    # Test 7: Multiple concurrent sessions for same user
    session2 = requests.Session()
    resp = session2.post(
        f"{base_url}/user/login",
        json={"email": user_email, "password": user_password}
    )
    assert_true(resp.status_code == 200, "Second login successful")
    
    session3 = requests.Session()
    resp = session3.post(
        f"{base_url}/user/login",
        json={"email": user_email, "password": user_password}
    )
    assert_true(resp.status_code == 200, "Third login successful")
    
    # Both sessions should work
    resp = session2.get(f"{base_url}/token")
    assert_true(resp.status_code == 200, "Session 2 works")
    
    resp = session3.get(f"{base_url}/token")
    assert_true(resp.status_code == 200, "Session 3 works")
    
    # Logout from session2 should not affect session3
    resp = session2.post(f"{base_url}/user/logout")
    assert_true(resp.status_code == 200, "Session 2 logout successful")
    
    resp = session2.get(f"{base_url}/token")
    assert_true(resp.status_code == 401, "Session 2 invalidated after logout")
    
    resp = session3.get(f"{base_url}/token")
    assert_true(resp.status_code == 200, "Session 3 still valid after session 2 logout")
    
    print("[OK] Logout invalidates only the specific session")
    
    print("[OK] Multiple concurrent sessions supported per user")
    
    # Cleanup
    session3.delete(f"{base_url}/user")


def main():
    print("== Scenario 12: Session Management ==")
    test_session_management()
    print("All checks passed.")


if __name__ == "__main__":
    main()
