def SequentialTask(*args, **kwargs):  # noqa: N802
    """Factory function for creating SequentialTask instances."""
    try:
        from crewai import Task
    except ImportError as e:
        msg = "CrewAI is not installed. Please install it with `uv pip install crewai`."
        raise ImportError(msg) from e

    return Task(*args, **kwargs)


def HierarchicalTask(*args, **kwargs):  # noqa: N802
    """Factory function for creating HierarchicalTask instances."""
    try:
        from crewai import Task
    except ImportError as e:
        msg = "CrewAI is not installed. Please install it with `uv pip install crewai`."
        raise ImportError(msg) from e

    return Task(*args, **kwargs)
