import { useTranslation } from "react-i18next";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { cn } from "@/utils/utils";

type CollaborationBetaToggleProps = {
  enabled: boolean;
  onEnabledChange: (enabled: boolean) => void;
  disabled?: boolean;
  className?: string;
};

export default function CollaborationBetaToggle({
  enabled,
  onEnabledChange,
  disabled = false,
  className,
}: CollaborationBetaToggleProps): JSX.Element {
  const { t } = useTranslation();

  return (
    <div
      className={cn(
        "flex max-w-xs items-start gap-2 rounded-md border bg-background px-3 py-2 shadow-sm",
        className,
      )}
      data-testid="collaboration-beta-toggle"
    >
      <Switch
        id="collaboration-operation-beta"
        checked={enabled}
        disabled={disabled}
        onCheckedChange={onEnabledChange}
        data-testid="collaboration-beta-switch"
      />
      <div className="space-y-0.5">
        <Label
          htmlFor="collaboration-operation-beta"
          className="text-xs font-medium leading-none"
        >
          {t("flow.collaboration.betaToggleLabel", {
            defaultValue: "Beta: operation-based collaborative editing",
          })}
        </Label>
        <p className="text-[11px] text-muted-foreground">
          {t("flow.collaboration.betaToggleDescription", {
            defaultValue:
              "Uses realtime operation batches instead of full-flow autosave. Turning this on reloads the flow from the server.",
          })}
        </p>
      </div>
    </div>
  );
}
