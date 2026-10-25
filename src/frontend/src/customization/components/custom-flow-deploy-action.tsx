interface CustomFlowDeployActionProps {
  /** The project the flow belongs to: a deployment is a project's, not one flow's. */
  projectId: string;
  flowId: string;
  flowName?: string;
}

// OSS no-op; the Enterprise overlay replaces this with a "Deploy to environment" item and dialog.
export default function CustomFlowDeployAction(_: CustomFlowDeployActionProps) {
  return null;
}
