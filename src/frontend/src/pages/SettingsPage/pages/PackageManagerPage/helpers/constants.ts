export const TEXTS = {
  // Page header
  PAGE_TITLE: "Package Manager",
  PAGE_DESCRIPTION:
    "Install Python packages into your Langflow environment using uv package manager.",

  // Install Package Card
  INSTALL_PACKAGE_TITLE: "Install Package",
  INSTALL_PACKAGE_DESCRIPTION:
    "Enter the name of a Python package to install it into your Langflow environment. The package will be available immediately after installation.",
  PACKAGE_INPUT_PLACEHOLDER:
    "Package name with optional version (e.g., pandas==2.3.1, requests>=2.25.0)",
  INSTALL_BUTTON_TEXT: "Install Package",
  INSTALLING_BUTTON_TEXT: "Installing...",
  VERSION_OPERATORS_TEXT: "Supported version operators:",
  VERSION_OPERATORS_LIST: [
    { operator: "==", description: "exact" },
    { operator: ">=", description: "minimum" },
    { operator: "<=", description: "maximum" },
    { operator: ">", description: "greater than" },
    { operator: "<", description: "less than" },
    { operator: "!=", description: "not equal" },
  ],
  NOTE_ALERT_TEXT:
    "Note: Packages are installed directly into your Langflow environment and will be available immediately for import in your flows. You cannot install packages that are already included as dependencies of Langflow.",

  // Confirmation Dialog
  CONFIRM_INSTALL_TITLE: "Confirm Package Installation",
  CONFIRM_INSTALL_DESCRIPTION: "Are you sure you want to install",
  CONFIRM_INSTALL_ACTIONS: "This will:",
  CONFIRM_INSTALL_ACTION_1: "Install the package using uv package manager",
  CONFIRM_INSTALL_ACTION_2:
    "Make the package available for import in your flows",
  CONFIRM_INSTALL_ACTION_3:
    "Complete without interrupting your current session",
  CANCEL_BUTTON_TEXT: "Cancel",

  // Progress Dialog
  PROGRESS_DIALOG_TITLE: "Installing Package",
  PROGRESS_DIALOG_DESCRIPTION:
    "Please wait while the package is being installed...",
  INSTALLING_PACKAGE_TEXT: "Installing",
  BACKEND_RESTARTING_TEXT: "Backend restarting with new dependencies...",
  INSTALLATION_IN_PROGRESS_TEXT: "Installation in progress...",
  CHECKING_STATUS_TEXT: "Checking installation status...",
  WAITING_COMPLETION_TEXT: "Waiting for installation to complete...",
  BACKEND_RESTART_ALERT_TEXT:
    "The backend is restarting to load new dependencies. This may take a moment to complete.",
  INSTALLATION_WAIT_ALERT_TEXT:
    "Please wait while the package is being installed. This process typically takes a few moments to complete.",

  // Success messages
  PACKAGE_INSTALLED_SUCCESS: (packageName: string) =>
    `Package '${packageName}' installed successfully! The package is now available for import.`,

  // Error messages
  PACKAGE_NAME_REQUIRED: "Package name is required",
  INSTALLATION_FAILED: "Installation Failed",
  UNKNOWN_ERROR: "Unknown error",
  PYTHON_VERSION_ERROR: (packageName: string) =>
    `Package '${packageName}' requires a different Python version than what's currently available. Please check the package documentation for compatibility requirements.`,
  DEPENDENCY_CONFLICT_ERROR: (packageName: string) =>
    `Package '${packageName}' has dependency conflicts that prevent installation. This may be due to version incompatibilities with existing packages.`,
} as const;

export const getVersionOperatorsText = () => {
  const operatorStrings = TEXTS.VERSION_OPERATORS_LIST.map(
    (item) => `${item.operator} (${item.description})`,
  );
  return `${TEXTS.VERSION_OPERATORS_TEXT} ${operatorStrings.join(", ")}`;
};
