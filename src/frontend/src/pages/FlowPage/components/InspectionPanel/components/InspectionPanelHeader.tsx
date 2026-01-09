import { Badge } from "@/components/ui/badge";
import { NodeIcon } from "@/CustomNodes/GenericNode/components/nodeIcon";
import type { NodeDataType } from "@/types/flow";

interface InspectionPanelHeaderProps {
  data: NodeDataType;
}

export default function InspectionPanelHeader({
  data,
}: InspectionPanelHeaderProps) {
  return (
    <div className="flex items-center justify-between border-b p-4">
      <div className="flex items-center gap-3">
        <NodeIcon
          dataType={data.type}
          icon={data.node?.icon}
          isGroup={!!data.node?.flow}
        />
        <div className="flex flex-col">
          <span className="font-semibold text-sm">
            {data.node?.display_name ?? data.type}
          </span>
          <span className="text-xs text-muted-foreground">
            Component Settings
          </span>
        </div>
      </div>
      <Badge variant="secondary" size="sm">
        ID: {data.id}
      </Badge>
    </div>
  );
}

// Made with Bob
