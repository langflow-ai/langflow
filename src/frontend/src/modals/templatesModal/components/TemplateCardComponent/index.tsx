import type { KeyboardEvent } from "react";
import { useTranslation } from "react-i18next";
import { convertTestName } from "@/components/common/storeCardComponent/utils/convert-test-name";
import DeleteConfirmationModal from "@/modals/deleteConfirmationModal";
import { swatchColors } from "@/utils/styleUtils";
import { cn, getNumberFromString } from "@/utils/utils";
import IconComponent, {
  ForwardedIconComponent,
} from "../../../../components/common/genericIconComponent";
import { Badge } from "../../../../components/ui/badge";
import type { TemplateCardComponentProps } from "../../../../types/templates/types";

interface TemplateCardComponentExtendedProps
  extends TemplateCardComponentProps {
  disabled?: boolean;
}

export default function TemplateCardComponent({
  example,
  onClick,
  onDelete,
  disabled = false,
}: TemplateCardComponentExtendedProps) {
  const { t } = useTranslation();
  const swatchIndex =
    (example.gradient && !isNaN(parseInt(example.gradient))
      ? parseInt(example.gradient)
      : getNumberFromString(example.gradient ?? example.name)) %
    swatchColors.length;

  const handleKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.currentTarget !== e.target) return;
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      if (!disabled) onClick();
    }
  };

  return (
    <div
      data-testid={`template-${convertTestName(example.name)}`}
      className={cn(
        "group flex gap-3 overflow-hidden rounded-md p-3 hover:bg-muted focus-visible:bg-muted",
        disabled ? "cursor-default opacity-80" : "cursor-pointer",
      )}
      role="button"
      aria-disabled={disabled}
      tabIndex={disabled ? -1 : 0}
      onKeyDown={handleKeyDown}
      onClick={() => !disabled && onClick()}
    >
      <div
        className={cn(
          "relative h-20 w-20 shrink-0 overflow-hidden rounded-md p-4 outline-none ring-ring",
          swatchColors[swatchIndex],
        )}
      >
        <IconComponent
          name={example.icon || "FileText"}
          className="absolute left-1/2 top-1/2 h-10 w-10 -translate-x-1/2 -translate-y-1/2 duration-300 group-hover:scale-105 group-focus-visible:scale-105"
        />
      </div>
      <div className="flex flex-1 flex-col justify-between">
        <div
          data-testid="text_card_container"
          role={convertTestName(example.name)}
        >
          <div className="flex w-full items-center">
            <h3
              className="line-clamp-3 font-semibold"
              data-testid={`template_${convertTestName(example.name)}`}
            >
              {example.name}
            </h3>
            {example.source === "team" && (
              <Badge variant="secondary" className="ml-2 shrink-0">
                {t("teamTemplates.team")}
              </Badge>
            )}
            {example.source === "team" && onDelete && (
              <DeleteConfirmationModal
                description={t("teamTemplates.deleteDescription", {
                  name: example.name,
                })}
                asChild
                onConfirm={(event) => {
                  event.preventDefault();
                  event.stopPropagation();
                  onDelete();
                }}
              >
                <button
                  type="button"
                  className="ml-auto rounded p-1 text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
                  aria-label={t("teamTemplates.delete")}
                  data-testid={`delete-team-template-${example.id}`}
                  onClick={(event) => event.stopPropagation()}
                  disabled={disabled}
                >
                  <ForwardedIconComponent name="Trash2" className="h-4 w-4" />
                </button>
              </DeleteConfirmationModal>
            )}
            <ForwardedIconComponent
              name="ArrowRight"
              className="mr-3 h-5 w-5 shrink-0 translate-x-0 opacity-0 transition-all duration-300 group-hover:translate-x-3 group-hover:opacity-100 group-focus-visible:translate-x-3 group-focus-visible:opacity-100"
            />
          </div>
          <p className="mt-2 line-clamp-2 text-sm text-muted-foreground">
            {example.description}
          </p>
        </div>
      </div>
    </div>
  );
}
