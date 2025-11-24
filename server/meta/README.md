## `run_bare.py`

Minimal FastAPI server instance without full initialization (no DB, jobs, OAuth setup).

**Purpose:** Generate OpenAPI/Swagger documentation without requiring database connections or environment variables.

**Usage:**
```bash
python3 -m meta.run_bare [port]
```

**Default port:** 8888

This registers all API routes but skips:
- PostgreSQL connection
- Background jobs (heartbeat, GCal polling)
- Session store initialization
- OAuth2 credential loading

Perfect for generating API documentation or testing route registration.
