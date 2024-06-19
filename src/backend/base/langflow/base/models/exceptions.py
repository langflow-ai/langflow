def get_message_from_openai_exception(exception: Exception) -> str:
    """
    Get a message from an OpenAI exception.

    Args:
        exception (Exception): The exception to get the message from.

    Returns:
        str: The message from the exception.
    """
    try:
        from openai import BadRequestError
    except ImportError:
        return
    if isinstance(exception, BadRequestError):
        message = exception.body.get("message")
        if message:
            return message
    return
