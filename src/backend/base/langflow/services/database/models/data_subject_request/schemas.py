from enum import Enum


class DataSubjectType(str, Enum):
    BUILDER = "builder"
    END_USER = "end_user"


class DataSubjectRequestStatus(str, Enum):
    REQUESTED = "requested"
    APPROVED = "approved"
    ERASING = "erasing"
    DONE = "done"
    REFUSED = "refused"
    WITHDRAWN = "withdrawn"


class DataSubjectRequestSource(str, Enum):
    SELF = "self"
    ADMIN = "admin"
    API = "api"


OPEN_STATUSES = (
    DataSubjectRequestStatus.REQUESTED,
    DataSubjectRequestStatus.APPROVED,
    DataSubjectRequestStatus.ERASING,
)
CLOSED_STATUSES = (
    DataSubjectRequestStatus.DONE,
    DataSubjectRequestStatus.REFUSED,
    DataSubjectRequestStatus.WITHDRAWN,
)
