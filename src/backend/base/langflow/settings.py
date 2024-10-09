DEV = False


def _set_dev(value):
    global DEV  # noqa: PLW0603
    DEV = value


def set_dev(value):
    _set_dev(value)
