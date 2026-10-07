"""Domain errors for data subject requests, each with a stable machine-readable code."""

from __future__ import annotations

from http import HTTPStatus


class DataSubjectError(Exception):
    """Base error. ``code`` is part of the public API contract; never rename a value."""

    code = "data_subject_error"
    status_code = HTTPStatus.BAD_REQUEST

    def __init__(self, message: str, *, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class InvalidEndUserIdError(DataSubjectError):
    code = "invalid_end_user_id"
    status_code = HTTPStatus.UNPROCESSABLE_ENTITY


class SubjectNotFoundError(DataSubjectError):
    code = "subject_not_found"
    status_code = HTTPStatus.NOT_FOUND


class SelfApprovalError(DataSubjectError):
    code = "self_approval"
    status_code = HTTPStatus.FORBIDDEN


class RequestNotFoundError(DataSubjectError):
    code = "request_not_found"
    status_code = HTTPStatus.NOT_FOUND


class InvalidTransitionError(DataSubjectError):
    code = "invalid_transition"
    status_code = HTTPStatus.CONFLICT


class DeployedResourcesError(DataSubjectError):
    code = "deployed_flows"
    status_code = HTTPStatus.CONFLICT


class LastAdministratorError(DataSubjectError):
    code = "last_administrator"
    status_code = HTTPStatus.CONFLICT


class ProtectedAccountError(DataSubjectError):
    code = "protected_account"
    status_code = HTTPStatus.CONFLICT


class FeatureDisabledError(DataSubjectError):
    code = "feature_disabled"
    status_code = HTTPStatus.NOT_FOUND


class ExportNotFoundError(DataSubjectError):
    code = "export_not_found"
    status_code = HTTPStatus.NOT_FOUND
