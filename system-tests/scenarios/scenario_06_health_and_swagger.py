#!/usr/bin/env python3
"""Scenario 6: Health check and API documentation validation."""
import sys
import subprocess
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
from utils import get_base_url, assert_true, wait_for_health


REPO_ROOT = Path(__file__).resolve().parents[2]
SERVER_DIR = REPO_ROOT / "server"
SWAGGER_MD = REPO_ROOT / "swagger.md"
OPENAPI_JSON = REPO_ROOT / "openapi.json"
GEN_SCRIPT = SERVER_DIR / "ops" / "swagger_gen.sh"


def test_healthz():
    """Test health check endpoint."""
    base_url = get_base_url()
    wait_for_health(base_url, timeout=60)


def generate_swagger():
    """Validate API documentation is available."""
    base_url = get_base_url()
    
    # First try reading from the running app
    try:
        resp = requests.get(f"{base_url.rstrip('/')}/openapi.json", timeout=10)
        if resp.status_code == 200 and resp.headers.get("content-type", "").startswith("application/json"):
            data = resp.json()
            assert_true(isinstance(data, dict) and "openapi" in data, "Fetched openapi.json from running app")
            return
        else:
            print(f"[WARN] GET /openapi.json returned {resp.status_code}, attempting generator script...")
    except Exception as e:
        print(f"[WARN] Failed to fetch /openapi.json from app: {e}. Attempting generator script...")

    # Fallback: run the swagger generation script
    assert_true(GEN_SCRIPT.exists(), f"Generator script exists: {GEN_SCRIPT}")
    proc = subprocess.run(
        ["bash", str(GEN_SCRIPT)],
        cwd=str(SERVER_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )
    print(proc.stdout)
    
    if proc.returncode == 0:
        assert_true(SWAGGER_MD.exists(), f"swagger.md generated at {SWAGGER_MD}")
        assert_true(SWAGGER_MD.stat().st_size > 0, "swagger.md is non-empty")
    else:
        if OPENAPI_JSON.exists() and OPENAPI_JSON.stat().st_size > 0:
            print("[WARN] swagger_gen.sh exited non-zero, but openapi.json was generated. "
                  "Ensure Node.js/npx is installed to build swagger.md")
        else:
            print(proc.stdout)
            assert_true(False, "swagger generation failed: neither swagger.md nor openapi.json present")


def main():
    print("== Scenario 6: Health and Swagger generation ==")
    test_healthz()
    generate_swagger()
    print("All checks passed.")


if __name__ == "__main__":
    main()
