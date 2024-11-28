from fastapi import HTTPException
from loguru import logger

from langflow.services.deps import get_settings_service


class MaxFileSizeException(HTTPException):
    def __init__(self, detail: str = "File size is larger than the maximum file size {}MB"):
        super().__init__(status_code=413, detail=detail)


# Adapted from https://github.com/steinnes/content-size-limit-asgi/blob/master/content_size_limit_asgi/middleware.py#L26
class ContentSizeLimitMiddleware:
    """Content size limiting middleware for ASGI applications.

    Args:
      app (ASGI application): ASGI application
      max_content_size (optional): the maximum content size allowed in bytes, None for no limit
      exception_cls (optional): the class of exception to raise (ContentSizeExceeded is the default)
    """

    def __init__(
        self,
        app,
    ):
        self.app = app
        self.logger = logger

    def receive_wrapper(self, receive):
        received = 0

        async def inner():
            max_file_size_upload = get_settings_service().settings.max_file_size_upload
            nonlocal received
            message = await receive()
            if message["type"] != "http.request" or max_file_size_upload is None:
                return message
            body_len = len(message.get("body", b""))
            received += body_len
            if received > max_file_size_upload * 1024 * 1024:
                # max_content_size is in bytes, convert to MB
                received_in_mb = round(received / (1024 * 1024), 3)
                msg = (
                    f"Content size limit exceeded. Maximum allowed is {max_file_size_upload}MB"
                    f" and got {received_in_mb}MB."
                )
                raise MaxFileSizeException(msg)
            return message

        return inner

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        wrapper = self.receive_wrapper(receive)
        await self.app(scope, wrapper, send)
