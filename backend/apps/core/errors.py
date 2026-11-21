from rest_framework.exceptions import APIException
from rest_framework.views import exception_handler


class DomainError(APIException):
    """Бизнес-ошибка с машиночитаемым кодом, например age_restriction."""

    status_code = 400

    def __init__(self, detail, code, status_code=None):
        super().__init__(detail=detail, code=code)
        if status_code:
            self.status_code = status_code


def api_exception_handler(exc, context):
    """Единый формат ошибок: {"detail": "...", "code": "...", "errors": {...}}"""
    response = exception_handler(exc, context)
    if response is None:
        return None
    data = response.data
    if isinstance(data, dict) and "detail" in data and len(data) <= 2:
        response.data = {"detail": str(data["detail"]), "code": getattr(data["detail"], "code", "error")}
    else:
        response.data = {"detail": "Проверьте введённые данные", "code": "validation_error", "errors": data}
    return response
