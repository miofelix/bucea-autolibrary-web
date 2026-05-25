from fastapi import Request, status
from fastapi.responses import JSONResponse


class AppError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
    ):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class NotFoundError(AppError):
    def __init__(self, message: str):
        super().__init__("not_found", message, status.HTTP_404_NOT_FOUND)


class ConflictError(AppError):
    def __init__(self, message: str):
        super().__init__("conflict", message, status.HTTP_409_CONFLICT)


class ConfigurationError(AppError):
    def __init__(self, message: str):
        super().__init__("configuration_error", message, status.HTTP_500_INTERNAL_SERVER_ERROR)


class ValidationAppError(AppError):
    def __init__(self, message: str):
        super().__init__("validation_error", message, status.HTTP_400_BAD_REQUEST)


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message}},
    )
