"""Common utilities for system tests."""
import os
import sys
import time
import requests


def get_base_url() -> str:
    return os.environ.get("BASE_URL", "http://localhost:8000")


def assert_true(cond: bool, msg: str):
    if not cond:
        print(f"[FAIL] {msg}")
        sys.exit(1)
    print(f"[OK] {msg}")


def wait_for_health(base_url: str = None, timeout: int = 30):
    if base_url is None:
        base_url = get_base_url()
    
    url = f"{base_url}/healthz"
    deadline = time.time() + timeout
    last_exc = None
    
    while time.time() < deadline:
        try:
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == "UP":
                    print(f"[OK] App is healthy at {base_url}")
                    return
        except Exception as e:
            last_exc = e
        time.sleep(1)
    
    print(f"[FAIL] App did not become healthy within {timeout}s. Last error: {last_exc}")
    sys.exit(1)