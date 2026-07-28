"""Framework-independent application errors."""


class ApplicationNotFoundError(LookupError):
    """A requested application resource does not exist."""


class ApplicationConflictError(RuntimeError):
    """The requested application mutation conflicts with current state."""


class AuthenticationError(PermissionError):
    """Credentials or a browser session did not authenticate a person."""


class AuthorizationError(PermissionError):
    """An authenticated principal may not perform an operation."""
