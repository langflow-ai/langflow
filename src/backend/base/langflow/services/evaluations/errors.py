class EvalsError(Exception):
    """Base for Evals domain errors; routes map each subclass to one HTTP status."""


class EvalsNotFoundError(EvalsError):
    """The resource does not exist or the caller cannot see it (404, never 403, to keep ids private)."""


class EvalsConflictError(EvalsError):
    """The request conflicts with current state, e.g. a duplicate name or a run already active (409)."""


class EvalsValidationError(EvalsError):
    """The request is well-formed but cannot be executed, e.g. an unsupported flow (422)."""
