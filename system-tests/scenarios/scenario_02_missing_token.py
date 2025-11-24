#!/usr/bin/env python3
"""Scenario 2: Negative - Missing token on data access."""
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
from utils import get_base_url, assert_true, wait_for_health


def test_missing_token():
    """Test that data endpoints require X-Data-Token header."""
    base_url = get_base_url()
    wait_for_health(base_url)
    
    # Attempt to list metrics without token
    resp = requests.get(f"{base_url}/data")
    assert_true(
        resp.status_code == 422,  # FastAPI returns 422 for missing header
        f"List metrics without token rejected (got {resp.status_code})"
    )
    
    # Attempt to ingest datapoints without token
    resp = requests.post(
        f"{base_url}/data/test_metric",
        json=[
            {
                "timestamp": 1234567890000,
                "dimensions": {"test": "value"},
                "value": 1.0
            }
        ]
    )
    assert_true(
        resp.status_code == 422,  # FastAPI returns 422 for missing header
        f"Ingest datapoints without token rejected (got {resp.status_code})"
    )
    
    # Attempt to query datapoints without token
    resp = requests.get(f"{base_url}/data/test_metric")
    assert_true(
        resp.status_code == 422,
        f"Query datapoints without token rejected (got {resp.status_code})"
    )


def main():
    print("== Scenario 2: Missing token on data access ==")
    test_missing_token()
    print("All checks passed.")


if __name__ == "__main__":
    main()
