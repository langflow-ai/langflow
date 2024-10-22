class CustomError(Exception):
    def __init__(self, detail: str, status_code: int):
        super().__init__(detail)
        self.status_code = status_code


# Define custom exceptions with status codes
class UnauthorizedError(CustomError):
    def __init__(self, detail: str = "Unauthorized access"):
        super().__init__(detail, 401)


class ForbiddenError(CustomError):
    def __init__(self, detail: str = "Forbidden"):
        super().__init__(detail, 403)


class APIKeyError(CustomError):
    def __init__(self, detail: str = "API key error"):
        super().__init__(detail, 400)  # ! Should be 401


class FilterError(CustomError):
    def __init__(self, detail: str = "Filter error"):
        super().__init__(detail, 400)
