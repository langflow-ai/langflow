import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import type { APIClassType } from "@/types/api";

function FooterButton({
  label,
  icon,
  onClick,
  testId,
}: {
  label: string;
  icon: string;
  onClick: () => void;
  testId?: string;
}): JSX.Element {
  return (
    <Button
      className="w-full flex cursor-pointer items-center justify-start gap-2 truncate py-2 text-xs text-muted-foreground px-3 hover:bg-accent group focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-inset focus-visible:ring-ring"
      unstyled
      data-testid={testId}
      onClick={onClick}
    >
      <div className="flex items-center gap-2 pl-1 group-hover:text-primary">
        {label}
        <ForwardedIconComponent
          name={icon}
          className="w-4 h-4 text-muted-foreground group-hover:text-primary"
        />
      </div>
    </Button>
  );
}

export interface ModelDropdownFooterProps {
  onRefresh: () => void;
  onManageProviders: () => void;
  /** External node whose icon labels the "connect other models" action; when absent that action is hidden. */
  externalNode: APIClassType | undefined;
  onConnectOtherModels: () => void;
}

/**
 * Footer actions of the model dropdown (refresh list, manage providers and the
 * optional connect-other-models entry). Kept out of the <Command> listbox so it
 * is not swept into the composite keyboard/focus model. Extracted from
 * ModelInputComponent (LE-1736 W26).
 */
export function ModelDropdownFooter({
  onRefresh,
  onManageProviders,
  externalNode,
  onConnectOtherModels,
}: ModelDropdownFooterProps): JSX.Element {
  const { t } = useTranslation();
  return (
    <div className="flex flex-col border-t border-border bg-background">
      <FooterButton
        label={t("modelInput.refreshList")}
        icon="RotateCw"
        onClick={onRefresh}
        testId="refresh-model-list"
      />
      <div className="bottom-0 bg-background">
        <FooterButton
          label={t("modelInput.manageProviders")}
          icon="Settings"
          onClick={onManageProviders}
          testId="manage-model-providers"
        />
      </div>
      {externalNode && (
        <div className="border-t bg-background">
          <FooterButton
            label={t("modelInput.connectOtherModels")}
            icon={externalNode.icon || "CornerDownLeft"}
            onClick={onConnectOtherModels}
            testId="connect-other-models"
          />
        </div>
      )}
    </div>
  );
}
