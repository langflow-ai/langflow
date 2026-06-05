import type { CustomCellRendererProps } from "ag-grid-react";
import { useTranslation } from "react-i18next";
import DateReader from "@/components/core/dateReaderComponent";

export default function LastUsedAtCellRender({
  value,
}: CustomCellRendererProps) {
  const { t } = useTranslation();

  if (value && typeof value === "string" && value.includes("T")) {
    return (
      <div className="flex h-full w-full items-center truncate">
        <DateReader date={value} />
      </div>
    );
  }

  return (
    <div className="flex h-full w-full items-center text-muted-foreground">
      {value ? value : t("settings.apiKeys.never")}
    </div>
  );
}
