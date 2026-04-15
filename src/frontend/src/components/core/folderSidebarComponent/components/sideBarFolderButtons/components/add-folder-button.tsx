import { useTranslation } from "react-i18next";
import IconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { Button } from "@/components/ui/button";

export const AddFolderButton = ({
  onClick,
  disabled,
  loading,
}: {
  onClick: () => void;
  disabled: boolean;
  loading: boolean;
}) => {
  const { t } = useTranslation();
  return (
    <ShadTooltip content={t("folder.createNewProject")} styleClasses="z-50">
      <Button
        variant="ghost"
        size="icon"
        className="h-7 w-7 border-0 text-muted-foreground hover:bg-muted"
        onClick={onClick}
        data-testid="add-project-button"
        disabled={disabled}
        loading={loading}
      >
        <IconComponent name="Plus" className="h-4 w-4" />
      </Button>
    </ShadTooltip>
  );
};
