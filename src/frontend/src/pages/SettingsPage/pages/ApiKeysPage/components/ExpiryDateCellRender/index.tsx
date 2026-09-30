import type { CustomCellRendererProps } from "ag-grid-react";
import { useTranslation } from "react-i18next";
import DateReader from "@/components/core/dateReaderComponent";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

export default function ExpiryDateCellRender({
  value,
}: CustomCellRendererProps) {
  const { t } = useTranslation();

  if (value) {
    return (
      <div className="flex h-full w-full items-center truncate">
        <DateReader date={value} />
      </div>
    );
  }

  return (
    <div className="flex h-full w-full items-center">
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>
            <span className="cursor-default select-none text-lg leading-none text-muted-foreground">
              ∞
            </span>
          </TooltipTrigger>
          <TooltipContent side="right">
            {t("apiKey.neverExpires", "This key never expires")}
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    </div>
  );
}
