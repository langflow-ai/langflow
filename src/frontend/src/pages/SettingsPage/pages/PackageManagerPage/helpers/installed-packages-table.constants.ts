export const TEXTS = {
  CARD_TITLE: "Installed Packages",
  CARD_DESCRIPTION: "Manage your installed Python packages",
  LOADING_DESCRIPTION: "Loading installed packages...",
  ERROR_DESCRIPTION: "Failed to load installed packages",

  TABLE_HEADER_PACKAGE_NAME: "Package Name",
  TABLE_HEADER_VERSION: "Version",

  EMPTY_STATE_TITLE: "No packages installed through the package manager",
  EMPTY_STATE_DESCRIPTION: "Install packages above to see them listed here",

  RESTORE_BUTTON_TEXT: "Restore Langflow",
  RESTORING_BUTTON_TEXT: "Restoring...",

  CONFIRM_RESTORE_TITLE: "Confirm Langflow Restore",
  CONFIRM_RESTORE_DESCRIPTION:
    "Are you sure you want to restore Langflow to its original state?",
  CONFIRM_RESTORE_WARNING: "Warning: This action will:",
  CONFIRM_RESTORE_ACTION_1: "Remove ALL user-installed packages",
  CONFIRM_RESTORE_ACTION_2: "Restore Langflow to its original dependencies",
  CONFIRM_RESTORE_ACTION_3: "Restart the backend",
  CONFIRM_RESTORE_ACTION_4: "Clear the package list",
  CONFIRM_RESTORE_IRREVERSIBLE: "This action cannot be undone.",
  CANCEL_BUTTON_TEXT: "Cancel",

  PROGRESS_DIALOG_TITLE: "Restoring Langflow",
  PROGRESS_DIALOG_DESCRIPTION:
    "Please wait while Langflow is being restored to its original state...",
  RESTORING_LANGFLOW_TEXT: "Restoring Langflow",
  RESTORE_IN_PROGRESS_TEXT: "Restore in progress...",
  CHECKING_RESTORE_STATUS_TEXT: "Checking restore status...",
  WAITING_RESTORE_COMPLETION_TEXT: "Waiting for restore to complete...",

  BACKEND_RESTART_REASON: "Backend restarted after Langflow restore",

  RESTORE_SUCCESS_TITLE:
    "Langflow restored successfully! All user-installed packages have been removed.",

  UNKNOWN_ERROR: "Unknown error",
  RESTORE_FAILED: "Restore Failed",
  RESTORE_TIMEOUT: "Restore Timeout",
  RESTORE_TIMEOUT_DESCRIPTION:
    "The restore operation took longer than expected. Please check if Langflow is running properly.",
  RESTORE_SYNC_FAILED:
    "Failed to restore Langflow. Please try again or contact support.",
} as const;
