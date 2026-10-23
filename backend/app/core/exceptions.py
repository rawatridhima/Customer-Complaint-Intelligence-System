class AppError(Exception):
    status_code: int = 500
    code: str = "internal_error"

    def __init__(self, message: str, details: list | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or []


class ValidationError(AppError):
    status_code, code = 422, "validation_error"


class NotFoundError(AppError):
    status_code, code = 404, "not_found"


class UnauthorisedError(AppError):
    status_code, code = 401, "unauthorised"


class ForbiddenError(AppError):
    status_code, code = 403, "forbidden"


class InvalidTransitionError(AppError):
    status_code, code = 409, "invalid_transition"


class ConfigurationError(AppError):
    status_code, code = 500, "configuration_error"


class LLMUnavailableError(AppError):
    status_code, code = 503, "llm_unavailable"


class LLMRateLimitedError(LLMUnavailableError):
    """The provider said "too many requests" (HTTP 429).

    daily=True means a daily quota is used up: retrying today will not help.
    retry_after is how long the provider asked us to wait, in seconds.
    """

    def __init__(self, message: str, retry_after: int = 60, daily: bool = False):
        super().__init__(message)
        self.retry_after = retry_after
        self.daily = daily


class ModelLoadError(AppError):
    status_code, code = 503, "model_unavailable"
