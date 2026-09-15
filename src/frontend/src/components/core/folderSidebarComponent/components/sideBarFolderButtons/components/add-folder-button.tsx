import { useState } from "react";
import { useTranslation } from "react-i18next";
import IconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { ProjectTypeType } from "@/pages/MainPage/entities";
import { ProjectStarterItem } from "./project-starter-item";

export const AddFolderButton = ({
  onClick,
  disabled,
  loading,
  projectTypes = [],
}: {
  /** Creates a project of the given type, or of the default type when none is given. */
  onClick: (projectType?: string) => void;
  disabled: boolean;
  loading: boolean;
  projectTypes?: ProjectTypeType[];
}) => {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const starters = projectTypes.flatMap((type) => type.starters ?? []);

  const button = (
    <Button
      variant="ghost"
      size="icon"
      className="h-7 w-7 border-0 text-muted-foreground hover:bg-muted"
      onClick={projectTypes.length > 1 ? undefined : () => onClick()}
      data-testid="add-project-button"
      aria-label={t("folder.createNewProject")}
      disabled={disabled}
      loading={loading}
    >
      <IconComponent name="Plus" className="h-4 w-4" />
    </Button>
  );

  // One type means there is nothing to choose, so the button stays a button.
  if (projectTypes.length <= 1) {
    return (
      <ShadTooltip content={t("folder.createNewProject")} styleClasses="z-50">
        {button}
      </ShadTooltip>
    );
  }

  return (
    // The tooltip wraps the menu rather than the trigger: DropdownMenuTrigger asChild needs to
    // hand its ref straight to the button.
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <ShadTooltip content={t("folder.createNewProject")} styleClasses="z-50">
        <DropdownMenuTrigger asChild>{button}</DropdownMenuTrigger>
      </ShadTooltip>
      <DropdownMenuContent className="w-[300px]" sideOffset={5} side="bottom">
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
        {starters.length > 0 && (
          <>
            <DropdownMenuSeparator />
            <DropdownMenuLabel>{t("projectStarters.label")}</DropdownMenuLabel>
            {starters.map((starter) => (
              <ProjectStarterItem
                key={starter.name}
                starter={starter}
                disabled={disabled || loading}
                onCreated={() => setOpen(false)}
              />
            ))}
          </>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
};
