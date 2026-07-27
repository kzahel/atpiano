"""Framework-independent application errors."""


class ApplicationNotFoundError(LookupError):
    """A requested application resource does not exist."""
