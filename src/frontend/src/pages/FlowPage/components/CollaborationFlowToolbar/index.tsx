import { useTranslation } from "react-i18next";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { Switch } from "@/components/ui/switch";
import { useOptionalFlowCollaborationContext } from "@/hooks/flows/flow-collaboration-context";
import { useCollaborationCollaborators } from "@/hooks/flows/use-collaboration-collaborators";
import CollaborationPresenceAvatars from "@/pages/FlowPage/components/CollaborationPresence";
import useAssistantManagerStore from "@/stores/assistantManagerStore";
import useFlowStore from "@/stores/flowStore";
import { cn } from "@/utils/utils";

export default function CollaborationFlowToolbar(): JSX.Element | null {
  const { t } = useTranslation();
  const collaboration = useOptionalFlowCollaborationContext();
  const collaborators = useCollaborationCollaborators();
  const isLocked = useFlowStore((state) => state.currentFlow?.locked);
  const isAssistantProcessing = useAssistantManagerStore(
    (state) => state.isAssistantProcessing,
  );
  const disabled = Boolean(isLocked || isAssistantProcessing);

  if (!collaboration) {
    return null;
  }

  const { betaEnabled, setBetaEnabled, collaborationStatus } = collaboration;

  return (
    <div
      className="flex items-center gap-2 border-r border-border pr-2"
      data-testid="collaboration-flow-toolbar"
    >
      {betaEnabled ? (
        <CollaborationPresenceAvatars
          collaborators={collaborators}
          connectionStatus={collaborationStatus}
        />
      ) : null}
      <ShadTooltip
        side="bottom"
        content={
          <div className="max-w-xs space-y-1 text-xs">
            <p className="font-medium">
              {t("flow.collaboration.betaToggleLabel", {
                defaultValue: "Beta: operation-based collaborative editing",
              })}
            </p>
            <p className="text-muted-foreground">
              {t("flow.collaboration.betaToggleDescription", {
                defaultValue:
                  "Uses realtime operation batches instead of full-flow autosave. Turning this on reloads the flow from the server.",
              })}
            </p>
          </div>
        }
      >
        <div className="flex items-center gap-1.5">
          <Switch
            id="collaboration-operation-beta-toolbar"
            checked={betaEnabled}
            disabled={disabled}
            onCheckedChange={(enabled) => {
              void setBetaEnabled(enabled);
            }}
            data-testid="collaboration-beta-switch"
            className={cn("scale-90")}
          />
        </div>
      </ShadTooltip>
    </div>
  );
}
