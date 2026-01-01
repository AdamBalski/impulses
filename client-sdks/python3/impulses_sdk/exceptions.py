class ImpulsesError(Exception):
    """Base exception for Impulses SDK errors."""
    pass


class AuthenticationError(ImpulsesError):
    """Raised when authentication fails (401)."""
    pass


class AuthorizationError(ImpulsesError):
    """Raised when authorization fails - insufficient capability (403)."""
    pass


class NotFoundError(ImpulsesError):
    """Raised when a resource is not found (404)."""
    pass


class ValidationError(ImpulsesError):
    """Raised when input validation fails (422)."""
    pass


class ServerError(ImpulsesError):
    """Raised when server returns 5xx error."""
    pass


class NetworkError(ImpulsesError):
    """Raised when network/connection fails."""
    pass