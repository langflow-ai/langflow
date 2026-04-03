import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Badge } from "@/components/ui/badge";
import ConnectionItem from "./connection-item";

interface FlowVersionItemProps {
  flowName: string | null;
  versionNumber: number;
  connectionNames: string[];
}

export default function FlowVersionItem({
  flowName,
  versionNumber,
  connectionNames,
}: FlowVersionItemProps) {
  return (
    <div className="flex flex-col gap-2 rounded-lg border border-border p-3">
      <div className="flex items-center gap-2">
        <ForwardedIconComponent
          name="Workflow"
          className="h-3.5 w-3.5 shrink-0 text-muted-foreground"
        />
        <span className="text-sm font-medium text-foreground">
          {flowName ?? "Unknown flow"}
        </span>
        <Badge
          variant="secondaryStatic"
          size="tag"
          className="bg-accent-purple-muted text-accent-purple-muted-foreground"
        >
          v{versionNumber}
        </Badge>
      </div>

      {connectionNames.length > 0 && (
        <div className="flex flex-col gap-1 pl-5">
          {connectionNames.map((name) => (
            <ConnectionItem key={name} name={name} />
          ))}
        </div>
      )}
    </div>
  );
}
