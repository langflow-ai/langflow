interface LogsSidebarGroupProps {
  selectedRunId: string | null;
  onSelectRun: (runId: string | null) => void;
}

/**
 * Sidebar group for logs — intentionally empty.
 * All logs UI lives in LogsMainContent.
 */
const LogsSidebarGroup = (_props: LogsSidebarGroupProps) => {
  return null;
};

export default LogsSidebarGroup;
