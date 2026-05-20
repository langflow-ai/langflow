import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Badge } from "@/components/ui/badge";
import { EditableToolName } from "./editable-tool-name";
import type { ReviewFlowItem } from "./types";

interface ReviewFlowConfigCardProps {
  item: ReviewFlowItem;
  onSaveToolName: (name: string) => void;
  toolError?: string;
  toolNameValue: string;
}

export function ReviewFlowConfigCard({
  item,
  onSaveToolName,
  toolError,
  toolNameValue,
}: ReviewFlowConfigCardProps) {
  const { t } = useTranslation();
  const newConnections = item.connectionDetails.filter(
    (connection) => connection.isNew,
  );
  const existingConnections = item.connectionDetails.filter(
    (connection) => !connection.isNew,
  );

  return (
    <div
      className={`rounded-xl border bg-background p-4 ${toolError ? "border-destructive/50" : "border-border"}`}
    >
      <div className="flex flex-col gap-3">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2">
            <ForwardedIconComponent
              name="Wrench"
              className={`h-3.5 w-3.5 shrink-0 ${toolError ? "text-destructive" : "text-muted-foreground"}`}
            />
            <EditableToolName
              onSave={onSaveToolName}
              placeholder={item.defaultToolName}
              value={toolNameValue}
            />
          </div>
          <div className="flex items-center gap-2 pl-5">
            <ForwardedIconComponent
              name="Workflow"
              className="h-3 w-3 shrink-0 text-muted-foreground"
            />
            <span className="text-xs text-muted-foreground">
              {item.flowName}
            </span>
            <Badge
              className="bg-accent-purple-muted text-accent-purple-muted-foreground"
              size="tag"
              variant="secondaryStatic"
            >
              {item.versionLabel}
            </Badge>
          </div>
        </div>

        {item.connectionDetails.length > 0 && (
          <div className="flex flex-col gap-4">
            {existingConnections.length > 0 && (
              <div className="flex flex-col gap-2">
                <span className="text-xs font-medium text-muted-foreground">
                  {t("deployments.existingConnections")}
                </span>
                {existingConnections.map((connection) => (
                  <span
                    key={connection.name}
                    className="text-xs font-medium text-foreground"
                  >
                    {connection.name}
                  </span>
                ))}
              </div>
            )}

            {newConnections.length > 0 && (
              <div className="flex flex-col gap-2">
                <span className="text-xs font-medium text-muted-foreground">
                  {t("deployments.newConnections")}
                </span>
                {newConnections.map((connection) => (
                  <div key={connection.name} className="flex flex-col gap-1.5">
                    <span className="text-xs font-medium text-foreground">
                      {connection.name}
                    </span>
                    {connection.envVars.length > 0 && (
                      <div className="flex flex-col divide-y divide-border overflow-hidden rounded-md border border-border">
                        {connection.envVars.map(({ key, masked }) => (
                          <div
                            key={key}
                            className="flex items-center justify-between bg-muted/40 px-3 py-1.5"
                          >
                            <span className="font-mono text-xs text-foreground">
                              {key}
                            </span>
                            <div className="flex items-center gap-2">
                              <span className="text-muted-foreground">=</span>
                              <span className="font-mono text-xs text-muted-foreground">
                                {masked}
                              </span>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {toolError && (
          <div className="flex items-center gap-2 rounded-lg border border-destructive/20 bg-destructive/5 px-3 py-2">
            <ForwardedIconComponent
              name="AlertTriangle"
              className="h-3.5 w-3.5 shrink-0 text-destructive"
            />
            <span className="text-xs text-destructive">{toolError}</span>
          </div>
        )}
      </div>
    </div>
  );
}
