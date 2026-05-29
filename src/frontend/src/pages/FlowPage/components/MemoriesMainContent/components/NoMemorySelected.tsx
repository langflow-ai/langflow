import { useTranslation } from "react-i18next";
import IconComponent from "@/components/common/genericIconComponent";

export const NoMemorySelected = () => {
  const { t } = useTranslation();
  return (
    <div
      className="flex h-full w-full flex-col items-center justify-center text-center"
      role="status"
      aria-live="polite"
      aria-atomic="true"
      aria-labelledby="no-memory-selected-title"
      aria-describedby="no-memory-selected-description"
    >
      <span aria-hidden="true">
        <IconComponent
          name="BrainCog"
          className="mb-3 h-12 w-12 text-muted-foreground opacity-50"
        />
      </span>
      <p
        id="no-memory-selected-title"
        className="text-sm text-muted-foreground"
      >
        {t("memory.noMemorySelected")}
      </p>
      <p
        id="no-memory-selected-description"
        className="mt-1 text-xs text-muted-foreground"
      >
        {t("memory.noMemorySelectedHint")}
      </p>
    </div>
  );
};
