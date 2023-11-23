class CustomException(Exception):
    def __init__(self, detail, status_code):
        super().__init__(detail)
        self.status_code = status_code


# Define custom exceptions with status codes
class UnauthorizedError(CustomException):
    def __init__(self, detail="Unauthorized access"):
        super().__init__(detail, 401)


class ForbiddenError(CustomException):
    def __init__(self, detail="Forbidden"):
        super().__init__(detail, 403)


class APIKeyError(CustomException):
    def __init__(self, detail="API key error"):
        super().__init__(detail, 400)  #! Should be 401


class FilterError(CustomException):
    def __init__(self, detail="Filter error"):
        super().__init__(detail, 400)
