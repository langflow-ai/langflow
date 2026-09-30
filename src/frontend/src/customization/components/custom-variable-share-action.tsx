interface CustomVariableShareActionProps {
  resourceId: string;
  resourceName: string;
}

// OSS no-op. Enterprise replaces this seam with variable share administration.
export default function CustomVariableShareAction(
  _: CustomVariableShareActionProps,
) {
  return null;
}
