import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import IconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { formatDateLabel } from "./traceViewHelpers";
import { DateRangePopoverProps } from "./types";

export function DateRangePopover({
  startDate,
  endDate,
  onStartDateChange,
  onEndDateChange,
}: DateRangePopoverProps) {
  const { t } = useTranslation();
  const rangeLabel = useMemo(() => {
    if (!startDate && !endDate) return "";
    if (startDate && !endDate)
      return t("trace.dateFrom", { date: formatDateLabel(startDate) });
    if (!startDate && endDate)
      return t("trace.dateUntil", { date: formatDateLabel(endDate) });
    return t("trace.dateRangeLabel", {
      start: formatDateLabel(startDate),
      end: formatDateLabel(endDate),
    });
  }, [startDate, endDate]);

  const hasInvalidRange = Boolean(startDate && endDate && endDate < startDate);

  const handleStartChange = (value: string) => {
    onStartDateChange(value);
  };

  const handleEndChange = (value: string) => {
    onEndDateChange(value);
  };

  const handleClearDates = () => {
    onStartDateChange("");
    onEndDateChange("");
  };

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          variant="ghost"
          size="sm"
          className="h-8 gap-2 px-2 text-muted-foreground"
          aria-label={t("trace.dateRange")}
        >
          <IconComponent name="Calendar" className="h-4 w-4" />
          <span className="inline-flex items-center gap-1 text-xs text-foreground">
            {rangeLabel}
            {hasInvalidRange ? (
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <span className="inline-flex h-4 w-4 items-center justify-center">
                      <IconComponent
                        name="AlertTriangle"
                        className="h-3 w-3 text-status-red"
                        aria-label={t("trace.invalidDateRange")}
                      />
                    </span>
                  </TooltipTrigger>
                  <TooltipContent>{t("trace.invalidDateRange")}</TooltipContent>
                </Tooltip>
              </TooltipProvider>
            ) : null}
          </span>
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-[260px] p-3">
        <div className="flex flex-col gap-2">
          <div className="flex flex-col gap-1">
            <span className="text-xs text-muted-foreground">
              {t("trace.startDate")}
            </span>
            <Input
              type="date"
              value={startDate}
              onChange={(e) => handleStartChange(e.target.value)}
              className="h-8 text-sm [color-scheme:light] dark:[color-scheme:white] dark:[&::-webkit-calendar-picker-indicator]:invert dark:[&::-webkit-calendar-picker-indicator]:opacity-80"
              aria-label={t("trace.startDate")}
            />
          </div>
          <div className="flex flex-col gap-1">
            <span className="text-xs text-muted-foreground">
              {t("trace.endDate")}
            </span>
            <Input
              type="date"
              value={endDate}
              onChange={(e) => handleEndChange(e.target.value)}
              className="h-8 text-sm [color-scheme:light] dark:[color-scheme:white] dark:[&::-webkit-calendar-picker-indicator]:invert dark:[&::-webkit-calendar-picker-indicator]:opacity-80"
              aria-label={t("trace.endDate")}
            />
          </div>
          {hasInvalidRange && (
            <span className="text-xs text-status-red">
              {t("trace.invalidDateRangeMessage")}
            </span>
          )}
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-7 justify-start px-1 text-xs text-muted-foreground"
            onClick={handleClearDates}
          >
            {t("trace.clearDates")}
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  );
}
