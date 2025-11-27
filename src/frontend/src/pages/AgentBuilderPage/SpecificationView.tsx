interface SpecificationViewProps {
  flowData: any;
  yamlSpec: string;
}

export default function SpecificationView({
  flowData,
  yamlSpec,
}: SpecificationViewProps) {
  return (
    <div className="h-full overflow-auto p-6">
      <div className="rounded-lg border bg-card">
        <div className="border-b px-4 py-3">
          <h3 className="font-semibold text-lg">Agent Specification (YAML)</h3>
        </div>
        <div className="p-4">
          <pre className="p-4 bg-background-surface rounded text-sm overflow-auto whitespace-pre font-mono">
            {yamlSpec || "No YAML specification available"}
          </pre>
        </div>
      </div>
    </div>
  );
}
