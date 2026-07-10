"""Shared exception hierarchy for RCP services."""


class RCPError(Exception):
    """Base class for domain errors raised by RCP services."""


class AuthError(RCPError):
    """Token missing, malformed, expired, or signed by an unknown key."""


class NotFoundError(RCPError):
    pass


class ConflictError(RCPError):
    pass


class UpstreamError(RCPError):
    """A dependent service returned an unexpected response."""
