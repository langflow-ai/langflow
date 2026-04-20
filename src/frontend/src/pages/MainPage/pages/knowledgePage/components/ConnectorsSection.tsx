import { useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { useGetConnectors } from "@/controllers/API/queries/knowledge-bases/use-get-connectors";
import S3ConnectorForm from "./S3ConnectorForm";

interface ConnectorsSectionProps {
  kbName: string;
}

/**
 * Compact connector picker that lives in the KB drawer.
 *
 * Phase 3A ships just the S3 connector form inline; later phases
 * (Google Drive, OneDrive, SharePoint) each add their own
 * connector-specific form + OAuth flow behind the same picker.
 */
const ConnectorsSection = ({ kbName }: ConnectorsSectionProps) => {
  const { data: connectors, isLoading } = useGetConnectors(undefined);
  const [activeType, setActiveType] = useState<string | null>(null);

  // Folder has its own dedicated endpoint + UI wired elsewhere; the
  // picker surfaces only cloud/remote connectors.
  const visibleConnectors =
    connectors?.filter((c) => c.source_type !== "folder") ?? [];

  return (
    <div className="space-y-3 px-4">
      <h4 className="text-sm font-medium">Ingest from a connector</h4>

      {isLoading && (
        <div className="text-sm text-muted-foreground">Loading connectors…</div>
      )}

      {!isLoading && visibleConnectors.length === 0 && (
        <div className="text-sm text-muted-foreground">
          No connectors available yet.
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        {visibleConnectors.map((connector) => {
          const selected = activeType === connector.source_type;
          return (
            <Button
              key={connector.source_type}
              type="button"
              variant={selected ? "default" : "outline"}
              size="sm"
              onClick={() =>
                setActiveType(selected ? null : connector.source_type)
              }
            >
              <ForwardedIconComponent
                name={connector.icon ?? "Plug"}
                className="mr-1 h-3.5 w-3.5"
              />
              {connector.display_name}
            </Button>
          );
        })}
      </div>

      {activeType === "s3" && (
        <S3ConnectorForm
          kbName={kbName}
          onSubmitted={() => setActiveType(null)}
        />
      )}

      {activeType && activeType !== "s3" && (
        <div className="rounded-md border border-dashed border-border p-3 text-xs text-muted-foreground">
          {connectors?.find((c) => c.source_type === activeType)?.display_name}{" "}
          support is coming in a later phase of this epic.
        </div>
      )}
    </div>
  );
};

export default ConnectorsSection;
