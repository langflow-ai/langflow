import { useTranslation } from "react-i18next";
import IconComponent from "@/components/common/genericIconComponent";
import { DropdownMenuItem } from "@/components/ui/dropdown-menu";
import { useCreateProjectStarter } from "@/controllers/API/queries/folders/use-create-project-starter";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import type { ProjectTypeType } from "@/pages/MainPage/entities";
import useAlertStore from "@/stores/alertStore";
import { extractApiErrorMessages } from "@/utils/apiError";

export function ProjectStarterItem({
  starter,
  disabled,
  onCreated,
}: {
  starter: NonNullable<ProjectTypeType["starters"]>[number];
  disabled: boolean;
  onCreated: () => void;
}) {
  const { t } = useTranslation();
  const navigate = useCustomNavigate();
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const { mutate, isPending } = useCreateProjectStarter();
  return (
    <DropdownMenuItem
      disabled={disabled || isPending}
      className="cursor-pointer items-start gap-2"
      onSelect={(event) => {
        event.preventDefault();
        mutate(starter.name, {
          onSuccess: (project) => {
            onCreated();
            navigate(`/all/folder/${project.id}?tab=harness`);
          },
          onError: (error) =>
            setErrorData({
              title: t("sidebar.projectCreateError"),
              list: extractApiErrorMessages(error),
            }),
        });
      }}
    >
      <IconComponent
        name={isPending ? "Loader2" : "BookOpenCheck"}
        className={`mt-0.5 h-4 w-4 shrink-0 text-muted-foreground ${isPending ? "animate-spin" : ""}`}
      />
      <div className="flex flex-col gap-1">
        <span>
          {t(`projectStarters.${starter.name}.title`, {
            defaultValue: starter.display_name,
          })}
        </span>
        <span className="text-xs text-muted-foreground">
          {t(`projectStarters.${starter.name}.description`, {
            defaultValue: starter.description,
          })}
        </span>
      </div>
    </DropdownMenuItem>
  );
}
