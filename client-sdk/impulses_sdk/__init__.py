"""Impulses SDK - Python client library for Impulses API."""

from .client import (
    ImpulsesClient
)

from .exceptions import (
    ImpulsesError,
    AuthenticationError,
    AuthorizationError,
    NotFoundError,
    ValidationError,
    ServerError,
    NetworkError,
)
from .models import Datapoint, DatapointSeries, ConstantImpulse
from .operations import compose_impulses

__version__ = "0.2.0"

__all__ = [
    "ImpulsesClient",
    "ImpulsesError",
    "AuthenticationError",
    "AuthorizationError",
    "NotFoundError",
    "ValidationError",
    "ServerError",
    "NetworkError",
    "Datapoint",
    "DatapointSeries",
    "ConstantImpulse",
    "compose_impulses"
]
