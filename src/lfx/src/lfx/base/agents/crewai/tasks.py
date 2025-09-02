try:
    from crewai import Task
except ImportError:
    Task = object


class SequentialTask(Task):
    pass


class HierarchicalTask(Task):
    pass
