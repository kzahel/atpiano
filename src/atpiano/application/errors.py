"""Framework-independent application errors."""

MAX_ERROR_MESSAGE_LENGTH = 500


def bounded_error_message(
    value: object,
    *,
    fallback: str = "The operation failed.",
) -> str:
    """Keep contract errors readable while preserving their final cause."""

    message = str(value).strip() or fallback
    if len(message) <= MAX_ERROR_MESSAGE_LENGTH:
        return message
    separator = " … "
    head_length = 160
    tail_length = MAX_ERROR_MESSAGE_LENGTH - head_length - len(separator)
    return (
        message[:head_length].rstrip()
        + separator
        + message[-tail_length:].lstrip()
    )


class ApplicationNotFoundError(LookupError):
    """A requested application resource does not exist."""


class ApplicationConflictError(RuntimeError):
    """The requested application mutation conflicts with current state."""


class AuthenticationError(PermissionError):
    """Credentials or a browser session did not authenticate a person."""


class AuthorizationError(PermissionError):
    """An authenticated principal may not perform an operation."""
