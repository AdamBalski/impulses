# System Tests

End-to-end integration tests for Impulses using Docker Compose.

## Structure

```
system-tests/
├── README.md                        # This file
├── .env.example                     # Template for test environment variables
├── .env                            # Local test config (gitignored)
├── docker-compose.test.yml         # Isolated test stack definition
├── tests.md                        # Test scenarios documentation
├── run_all.py                      # Test runner (executes all scenarios)
├── utils.py                        # Common test utilities
└── scenarios/                      # Test scenario implementations (18 total)
    ├── scenario_01_happy_path.py              # User lifecycle and data ingestion
    ├── scenario_02_missing_token.py           # Missing token rejection
    ├── scenario_03_insufficient_capability.py # Capability enforcement
    ├── scenario_04_token_expiry.py            # Token expiration
    ├── scenario_05_token_deletion.py          # Token deletion
    ├── scenario_06_health_and_swagger.py      # Health & API docs
    ├── scenario_07_multi_user_isolation.py    # Multi-user data isolation
    ├── scenario_08_invalid_metric_names.py    # Metric name validation
    ├── scenario_09_invalid_payloads.py        # Payload validation
    ├── scenario_10_token_name_conflicts.py    # Token naming
    ├── scenario_11_api_capability.py          # API vs INGEST capability
    ├── scenario_12_session_management.py      # Login/logout sessions
    ├── scenario_13_metric_deletion.py         # Metric deletion
    ├── scenario_14_auth_edge_cases.py         # Auth validation
    ├── scenario_15_sdk_usage.py               # Client SDK integration
    ├── scenario_16_sdk_exceptions.py          # SDK error handling
    ├── scenario_17_dimension_validation.py    # Dimension validation
    └── scenario_18_sdk_fluent_api.py          # SDK fluent API & chaining
```

## Quick Start

### 1. Setup Environment

```bash
cd system-tests
cp .env.example .env
# Edit .env and set TOKEN, HASHED_TOKEN, GOOGLE_OAUTH2_CREDS
```

### 2. Run Tests

From repository root:

```bash
# Run all scenarios
make system-tests

# Run specific scenarios by number
make system-tests TESTS="-n 1"              # Run only scenario 1
make system-tests TESTS="-n 1,3,5"          # Run scenarios 1, 3, and 5
make system-tests TESTS="-n 1-5"            # Run scenarios 1 through 5
make system-tests TESTS="-n 1-5,15-18"      # Run scenarios 1-5 and 15-18

# Run scenarios by pattern
make system-tests TESTS="-p '*sdk*'"        # Run SDK-related scenarios
make system-tests TESTS="-p '*auth*'"       # Run auth-related scenarios

# List available scenarios
make system-tests TESTS="-l"
```

This will:
- Build the app Docker image
- Start PostgreSQL and app services (isolated, no host ports)
- Run selected test scenarios in a tester container
- Tear down everything (including volumes)

## Running Tests Locally (Without Docker)

For faster iteration during development, you can run tests directly against a local server:

```bash
# Start the server locally first
cd server
./ops/deploy.sh

# In another terminal, run specific scenarios
cd system-tests
export BASE_URL=http://localhost:8000

# List scenarios
python run_all.py -l

# Run specific scenarios
python run_all.py -n 1                    # Run scenario 1
python run_all.py -n 1-5                  # Run scenarios 1-5
python run_all.py -n 1,3,5,15             # Run specific scenarios
python run_all.py -p '*sdk*'              # Run SDK scenarios
python run_all.py -p '*auth*'             # Run auth scenarios
python run_all.py                         # Run all scenarios
```

**Benefits of local testing:**
- Faster iteration (no Docker build/teardown)
- Easier debugging (direct access to logs)
- Can keep server state between test runs

**Note:** Local tests will modify your local database and data-store. Use Docker tests for clean, isolated runs.

## Test Environment

### Docker Services

**postgres**
- Image: `postgres:15-alpine`
- Database: `impulses`
- No exposed ports (internal network only)
- Ephemeral volume (deleted after tests)

**app**
- Built from `../server/Dockerfile`
- No exposed ports (internal network only)
- Migrations run automatically on startup
- Ephemeral data-store volume

**tester**
- Image: `python:3.11-slim`
- Installs `requests` library
- Runs `system-tests/run_all.py`
- Accesses app via `http://app:8000`

### Environment Variables

Required in `.env`:

- `TOKEN` - Application auth token (generate with `secrets.token_urlsafe(32)`)
- `HASHED_TOKEN` - Bcrypt hash of TOKEN (remember to escape `$` as `$$`)
- `GOOGLE_OAUTH2_CREDS` - Google OAuth2 JSON (dummy values OK for tests)

Optional:

- `POSTGRES_DB` - Database name (default: `impulses`)
- `POSTGRES_USER` - Database user (default: `impulses_user`)
- `POSTGRES_PASSWORD` - Database password (default: `impulses_password`)
- `SESSION_TTL_SEC` - Session duration (default: `1800`)

## Writing Tests

### Adding a New Scenario

1. Create `scenarios/scenario_XX_description.py`:

```python
#!/usr/bin/env python3
"""Scenario XX: Brief description of what this tests."""
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
from utils import get_base_url, assert_true, wait_for_health

def test_your_scenario():
    """Test description."""
    base_url = get_base_url()
    wait_for_health(base_url)
    
    # Your test logic here
    resp = requests.get(f"{base_url}/healthz")
    assert_true(resp.status_code == 200, "Health check passed")

def main():
    print("== Scenario XX: Description ==")
    test_your_scenario()
    print("All checks passed.")

if __name__ == "__main__":
    main()
```

2. Add to `run_all.py`:

```python
SCENARIOS = [
    SCENARIOS_DIR / "scenario_01_happy_path.py",
    SCENARIOS_DIR / "scenario_06_health_and_swagger.py",
    SCENARIOS_DIR / "scenario_XX_description.py",  # Add your scenario
]
```

3. Run tests:

```bash
make system-tests
```

### Common Utilities (utils.py)

The `utils.py` module provides helper functions for all scenarios:

- **`get_base_url()`** - Returns the app base URL from `BASE_URL` env var
- **`assert_true(cond, msg)`** - Assert condition with descriptive message
- **`wait_for_health(base_url, timeout)`** - Wait for `/healthz` to return UP
- **`parse_datapoints_response(json)`** - Parse datapoints from API response (handles both list and RootModel formats)

Import these in your scenarios:

```python
from utils import get_base_url, assert_true, wait_for_health, parse_datapoints_response
```

### Test Guidelines

- **Use utils**: Import common functions from `utils.py` instead of duplicating code
- **Wait for health**: Call `wait_for_health()` at the start of tests
- **Use sessions**: `requests.Session()` for cookie handling
- **Unique identifiers**: Use timestamps to avoid conflicts between runs
- **Clean up**: Tests run in isolation, so cleanup is optional
- **Descriptive assertions**: Include actual/expected values in messages
- **Exit codes**: `sys.exit(1)` on failure, `sys.exit(0)` on success

## Debugging

### View Logs

```bash
# While tests are running (in another terminal)
docker-compose -p impulses-test -f system-tests/docker-compose.test.yml logs -f app

# After failure (before cleanup)
make system-tests-clean  # Clean up if needed
```

### Run Single Scenario

```bash
# Start services manually
docker-compose -p impulses-test -f system-tests/docker-compose.test.yml --env-file system-tests/.env up -d postgres app

# Wait for health
docker-compose -p impulses-test -f system-tests/docker-compose.test.yml exec app wget -qO- http://localhost:8000/healthz

# Run tester with bash for debugging
docker-compose -p impulses-test -f system-tests/docker-compose.test.yml run --rm tester bash

# Inside container:
pip install requests
python system-tests/scenarios/scenario_01_happy_path.py

# Cleanup
docker-compose -p impulses-test -f system-tests/docker-compose.test.yml --env-file system-tests/.env down -v
```

### Common Issues

**Issue**: Tests fail with 401 on data access
- **Fix**: Check `X-Data-Token` header format: `<name>:<plaintext>`

**Issue**: App container exits immediately
- **Fix**: Check app logs for startup errors (missing env vars, DB connection)

**Issue**: Tester can't resolve `app` hostname
- **Fix**: Ensure tester depends on app with `condition: service_healthy`

**Issue**: Token hash validation fails
- **Fix**: Escape `$` in `.env` file: `$$2b$$12$$...`

## CI/CD Integration

### GitHub Actions Example

```yaml
jobs:
  system-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup test environment
        run: |
          cd system-tests
          cp .env.example .env
          # Set required env vars from secrets
          echo "TOKEN=${{ secrets.TEST_TOKEN }}" >> .env
          echo "HASHED_TOKEN=${{ secrets.TEST_HASHED_TOKEN }}" >> .env
          echo "GOOGLE_OAUTH2_CREDS='${{ secrets.GOOGLE_OAUTH2_CREDS }}'" >> .env
      
      - name: Run system tests
        run: make system-tests
```

## Available Scenarios

### Scenario 1: Happy Path - User Lifecycle and Data Ingestion
- User creation and authentication
- Login and session management
- Token creation with SUPER capability
- Data ingestion with token auth
- Metric listing and querying
- Token deletion and verification
- User deletion and cleanup verification

### Scenario 2: Missing Token on Data Access (Negative)
- Attempt to list metrics without `X-Data-Token`
- Attempt to ingest datapoints without `X-Data-Token`
- Attempt to query datapoints without `X-Data-Token`
- Validates 422 responses for missing required header

### Scenario 3: Insufficient Capability (Negative)
- Create INGEST-only token
- Attempt to read metrics with INGEST token (requires API capability)
- Attempt to query datapoints with INGEST token
- Verify INGEST token can still write data
- Validates 403 Forbidden for insufficient capability

### Scenario 4: Token Expiry
- Create token with short TTL (2 seconds)
- Verify token works before expiry
- Wait for token to expire
- Attempt to use expired token
- Validates 401 Unauthorized for expired tokens

### Scenario 5: Token Deletion
- Create token and use it for data ingestion
- Delete token via API
- Attempt to write data with deleted token
- Attempt to read data with deleted token
- Validates 401 Unauthorized after deletion

### Scenario 6: Health and Swagger
- Health check endpoint validation (`/healthz`)
- OpenAPI spec generation and validation
- API documentation verification

### Scenario 7: Multi-User Data Isolation
- Create two separate users with their own tokens
- Both users ingest to metrics with same name
- Verify each user sees only their own data
- Validates complete data isolation between users

### Scenario 8: Invalid Metric Names
- Reserved prefix `imp.*` rejected (403)
- Empty metric name validation
- Invalid characters validation
- Length validation (>100 chars rejected)
- Valid edge cases (99 chars, special chars)

### Scenario 9: Invalid Data Payloads
- Invalid dimension keys (spaces, special chars)
- Empty datapoints array handling
- Invalid timestamp formats
- Invalid value types (string, null)
- Missing required fields (timestamp, value, dimensions)
- Valid payload acceptance (sanity check)

### Scenario 10: Token Name Conflicts
- Duplicate token name for same user (rejected)
- Different users can have tokens with same name
- List tokens shows only user's own tokens
- Token isolation verified

### Scenario 11: API vs INGEST Capability
- Create API token (read-only capability)
- API token can list and query metrics
- API token CANNOT ingest data (403)
- API token CANNOT delete metrics (403)
- Clear separation of read/write permissions

### Scenario 12: Session Management
- Login and session cookie handling
- Session-based access to protected endpoints
- Logout invalidation (if implemented)
- Multiple concurrent sessions per user
- Session isolation (logout one doesn't affect others)

### Scenario 13: Metric Deletion
- Ingest data to metric
- Verify metric appears in list
- Delete metric via API
- Verify metric removed from list
- Query returns empty or 404 after deletion

### Scenario 14: Authentication Edge Cases
- Wrong password rejection (401)
- Non-existent email rejection (401)
- Duplicate email rejection (409/500)
- Invalid email format handling
- Empty email handling
- Missing email/password fields (422)
- Empty password handling
- Invalid role rejection (422)

### Scenario 15: Client SDK Usage
- Initialize SDK client with token authentication
- Upload datapoints using SDK
- List metrics using SDK
- Fetch datapoints using SDK
- SDK data operations (filter, map)
- Incremental uploads and queries
- Delete metrics using SDK
- Empty metric handling

### Scenario 16: SDK Exception Handling
- ValueError for empty initialization parameters
- AuthenticationError for invalid tokens
- AuthorizationError for insufficient capability
- NotFoundError for non-existent resources
- ValidationError for invalid input
- NetworkError for connection failures
- Exception inheritance (all inherit from ImpulsesError)
- Comprehensive error messages

### Scenario 17: Dimension Validation
- Empty dimensions object accepted
- Long dimension values (1000 chars)
- Many dimensions (15+ keys)
- Special characters in dimension values
- Unicode support in dimension values
- Dimension key length validation (>100 chars rejected)
- Empty dimension key rejection
- Dimension preservation in storage

### Scenario 18: SDK Fluent API
- Fluent `prefix_op()` method (cumulative operations)
- Fluent `sliding_window()` method (rolling windows)
- Method chaining (filter → map → sliding_window → prefix_op)
- Complex chaining with multiple operations
- Backward compatibility with legacy `operations` module
- Cumulative sum verification
- Rolling window calculations

## See Also

- [tests.md](./tests.md) - Detailed scenario descriptions
- [../DOCKER.md](../DOCKER.md) - Production Docker setup
- [../server/README.md](../server/README.md) - Server documentation
