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


class ModelLoadError(AppError):
    status_code, code = 503, "model_unavailable"
