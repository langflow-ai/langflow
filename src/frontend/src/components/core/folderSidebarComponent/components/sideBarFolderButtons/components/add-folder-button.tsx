import { useTranslation } from "react-i18next";
import IconComponent from "@/components/common/genericIconComponent";
import { BlockableButton } from "@/components/core/triggers/BlockableButton";

// Plus button that creates a project. A blocked reason explains why it is unavailable.
export const AddFolderButton = ({
  onClick,
  disabled,
  loading,
  blockedReason,
}: {
  onClick: () => void;
  disabled: boolean;
  loading: boolean;
  blockedReason?: string;
}) => {
  const { t } = useTranslation();
  return (
    <BlockableButton
      variant="ghost"
      size="icon"
      className="h-7 w-7 border-0 text-muted-foreground hover:bg-muted"
      onClick={onClick}
      data-testid="add-project-button"
      aria-label={t("folder.createNewProject")}
      tooltip={t("folder.createNewProject")}
      blockedReason={blockedReason || undefined}
      disabled={disabled}
      loading={loading}
    >
      <IconComponent name="Plus" className="h-4 w-4" />
    </BlockableButton>
  );
};
