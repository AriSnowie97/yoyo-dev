"""Domain errors — raised when a business rule is violated."""


class DomainError(Exception):
    """Base class for every business-rule violation."""


class InvalidValue(DomainError):
    """A value object was built from an out-of-range or malformed value."""


class UnknownTrick(DomainError):
    """The requested trick does not exist."""


class NoActiveTask(DomainError):
    """An operation needs a running task, but the agent is not working."""


class TrickOnCooldown(DomainError):
    """Tricks are being requested faster than the yo-yo can perform them."""
