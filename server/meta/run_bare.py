"""
Lightweight FastAPI app instance for generating OpenAPI documentation.
Skips all initialization (DB, jobs, OAuth, etc.) and only registers routes.
"""

import fastapi
from src.resources import data, user, token, google_oauth2

def create_bare_app() -> fastapi.FastAPI:
    """Create minimal FastAPI app with routes but no dependencies."""
    app = fastapi.FastAPI(
        title="Impulses API",
        description="Metric tracking and analytics platform",
        version="1.0.0"
    )
    
    # Register routers without dependency injection
    app.include_router(google_oauth2.router, prefix="/oauth2/google", tags=["OAuth2"])
    app.include_router(data.router, prefix="/data", tags=["Data"])
    app.include_router(user.router, prefix="/user", tags=["User Management"])
    app.include_router(token.router, prefix="/token", tags=["Token Management"])
    
    @app.get("/healthz", tags=["Health"])
    async def healthz():
        """Health check endpoint."""
        return {"status": "UP"}
    
    return app

if __name__ == "__main__":
    import uvicorn
    import sys
    
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8888
    
    app = create_bare_app()
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")
