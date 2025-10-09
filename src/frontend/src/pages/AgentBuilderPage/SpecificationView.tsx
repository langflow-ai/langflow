interface SpecificationViewProps {
  flowData: any;
}

export default function SpecificationView({ flowData }: SpecificationViewProps) {
  // Extract information from flow data
  const name = flowData?.name || "Untitled Agent";
  const description = flowData?.description || "No description";
  const isComponent = flowData?.is_component || false;
  const updatedAt = flowData?.updated_at || null;
  const metadata = flowData?.metadata || {};
  const tags = flowData?.metadata?.tags || [];

  // Extract nodes and edges
  const nodes = flowData?.data?.nodes || [];
  const edges = flowData?.data?.edges || [];

  // Try to find model configuration from nodes
  const findModelConfig = () => {
    const modelNode = nodes.find((n: any) =>
      n.data?.type?.includes('Model') ||
      n.data?.node?.template?.model_name
    );
    return modelNode?.data?.node?.template || {};
  };

  const modelConfig = findModelConfig();

  return (
    <div className="h-full overflow-auto p-6 space-y-6">
      {/* Basic Info */}
      <div className="rounded-lg border bg-card p-4">
        <h3 className="font-semibold mb-4 text-lg">Basic Info</h3>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="text-sm text-muted-foreground">Agent Name</label>
            <div className="text-sm font-medium">{name}</div>
          </div>
          <div>
            <label className="text-sm text-muted-foreground">Category</label>
            <div className="text-sm font-medium">{metadata.category || metadata.kind || 'General'}</div>
          </div>
          <div>
            <label className="text-sm text-muted-foreground">Owner</label>
            <div className="text-sm font-medium">{metadata.owner || 'System'}</div>
          </div>
          <div>
            <label className="text-sm text-muted-foreground">Status</label>
            <div className="text-sm font-medium">{isComponent ? 'Component' : 'Published'}</div>
          </div>
          <div className="col-span-2">
            <label className="text-sm text-muted-foreground">Description</label>
            <div className="text-sm">{description}</div>
          </div>
        </div>
      </div>

      {/* Tags */}
      {tags && tags.length > 0 && (
        <div className="rounded-lg border bg-card p-4">
          <h3 className="font-semibold mb-4 text-lg">Tags</h3>
          <div className="flex flex-wrap gap-2">
            {tags.map((tag: string, idx: number) => (
              <span
                key={idx}
                className="rounded-full bg-muted px-3 py-1 text-sm text-muted-foreground"
              >
                {tag}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Core Configuration */}
      <div className="rounded-lg border bg-card p-4">
        <h3 className="font-semibold mb-4 text-lg">Core Configuration</h3>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="text-sm text-muted-foreground">Input Type</label>
            <div className="text-sm font-medium">{metadata.inputType || 'Text'}</div>
          </div>
          <div>
            <label className="text-sm text-muted-foreground">Output Type</label>
            <div className="text-sm font-medium">{metadata.outputType || 'Text Response'}</div>
          </div>
          <div className="col-span-2">
            <label className="text-sm text-muted-foreground">Persona/Role</label>
            <div className="text-sm">{metadata.persona || metadata.agentGoal || 'General assistant'}</div>
          </div>
        </div>
      </div>

      {/* Model & Settings */}
      {modelConfig && Object.keys(modelConfig).length > 0 && (
        <div className="rounded-lg border bg-card p-4">
          <h3 className="font-semibold mb-4 text-lg">Model & Settings</h3>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="text-sm text-muted-foreground">Model</label>
              <div className="text-sm font-medium">
                {modelConfig.model_name?.value || 'GPT-4'}
              </div>
            </div>
            <div>
              <label className="text-sm text-muted-foreground">Temperature (seconds)</label>
              <div className="text-sm font-medium">
                {modelConfig.temperature?.value || '0.7'}
              </div>
            </div>
            <div>
              <label className="text-sm text-muted-foreground">Max. Tokens</label>
              <div className="text-sm font-medium">
                {modelConfig.max_tokens?.value || '2048'}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Version Information */}
      <div className="rounded-lg border bg-card p-4">
        <h3 className="font-semibold mb-4 text-lg">Version Information</h3>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="text-sm text-muted-foreground">Version</label>
            <div className="text-sm font-medium">{metadata.version || '1.0'}</div>
          </div>
          <div>
            <label className="text-sm text-muted-foreground">Last Modified</label>
            <div className="text-sm font-medium">
              {updatedAt ? new Date(updatedAt).toLocaleString() : 'N/A'}
            </div>
          </div>
        </div>
      </div>

      {/* Components */}
      <div className="rounded-lg border bg-card p-4">
        <h3 className="font-semibold mb-4 text-lg">Components ({nodes.length})</h3>
        <div className="space-y-2">
          {nodes.map((node: any, idx: number) => (
            <div key={idx} className="flex items-center gap-3 p-2 rounded bg-muted/50">
              <div className="flex-1">
                <div className="text-sm font-medium">{node.data?.display_name || node.data?.type || 'Component'}</div>
                <div className="text-xs text-muted-foreground">{node.data?.description || node.id}</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Connections */}
      {edges.length > 0 && (
        <div className="rounded-lg border bg-card p-4">
          <h3 className="font-semibold mb-4 text-lg">Connections ({edges.length})</h3>
          <div className="space-y-2">
            {edges.map((edge: any, idx: number) => (
              <div key={idx} className="text-sm p-2 rounded bg-muted/50">
                <span className="font-medium">{edge.source}</span>
                <span className="mx-2 text-muted-foreground">→</span>
                <span className="font-medium">{edge.target}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Raw JSON (collapsible) */}
      <details className="rounded-lg border bg-card p-4">
        <summary className="font-semibold cursor-pointer">Raw JSON (Advanced)</summary>
        <pre className="mt-4 p-4 bg-muted/50 rounded text-xs overflow-auto">
          {JSON.stringify(flowData, null, 2)}
        </pre>
      </details>
    </div>
  );
}
