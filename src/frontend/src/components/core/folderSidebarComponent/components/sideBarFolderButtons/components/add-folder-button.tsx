import { useTranslation } from "react-i18next";
import IconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { BlockableButton } from "@/components/core/triggers/BlockableButton";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { ProjectTypeType } from "@/pages/MainPage/entities";

// Plus button that creates a project. A blocked reason explains why it is unavailable.
export const AddFolderButton = ({
  onClick,
  disabled,
  loading,
  blockedReason,
  projectTypes = [],
}: {
  /** Creates a project of the given type, or of the default type when none is given. */
  onClick: (projectType?: string) => void;
  disabled: boolean;
  loading: boolean;
  blockedReason?: string | null;
  projectTypes?: ProjectTypeType[];
}) => {
  const { t } = useTranslation();
  const buttonProps = {
    variant: "ghost",
    size: "icon",
    className: "h-7 w-7 border-0 text-muted-foreground hover:bg-muted",
    "data-testid": "add-project-button",
    "aria-label": t("folder.createNewProject"),
    disabled,
    loading,
  } as const;
  const icon = <IconComponent name="Plus" className="h-4 w-4" />;

  // One type means there is nothing to choose, and a blocked button has no menu to open.
  if (projectTypes.length <= 1 || blockedReason) {
    return (
      <BlockableButton
        {...buttonProps}
        onClick={() => onClick()}
        tooltip={t("folder.createNewProject")}
        blockedReason={blockedReason}
      >
        {icon}
      </BlockableButton>
    );
  }

  return (
    // The tooltip wraps the menu rather than the trigger: DropdownMenuTrigger asChild needs to
    // hand its ref straight to the button.
    <DropdownMenu>
      <ShadTooltip content={t("folder.createNewProject")} avoidCollisions>
        <DropdownMenuTrigger asChild>
          <Button {...buttonProps}>{icon}</Button>
        </DropdownMenuTrigger>
      </ShadTooltip>
      <DropdownMenuContent className="w-[240px]" sideOffset={5} side="bottom">
        {projectTypes.map((projectType) => (
          <DropdownMenuItem
            key={projectType.name}
            data-testid={`add-project-${projectType.name}`}
            className="cursor-pointer items-start gap-2"
            onSelect={() => onClick(projectType.name)}
          >
            {projectType.icon && (
              <IconComponent
                name={projectType.icon}
                className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground"
              />
            )}
            <div className="flex flex-col">
              <span>{projectType.display_name}</span>
              <span className="text-xs text-muted-foreground">
                {projectType.description}
              </span>
            </div>
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
};
