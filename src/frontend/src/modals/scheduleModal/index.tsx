import { useEffect, useMemo, useState } from "react";
import IconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { useCreateSchedule } from "@/controllers/API/queries/schedules/use-create-schedule";
import { useDeleteSchedule } from "@/controllers/API/queries/schedules/use-delete-schedule";
import { useGetSchedule } from "@/controllers/API/queries/schedules/use-get-schedule";
import { useUpdateSchedule } from "@/controllers/API/queries/schedules/use-update-schedule";
import useAlertStore from "@/stores/alertStore";
import BaseModal from "../baseModal";

type ScheduleModalProps = {
  open: boolean;
  setOpen: (open: boolean) => void;
  flowId: string;
};

const FREQUENCY_OPTIONS = [
  { value: "every_minute", label: "Every minute" },
  { value: "every_5_minutes", label: "Every 5 minutes" },
  { value: "every_15_minutes", label: "Every 15 minutes" },
  { value: "every_30_minutes", label: "Every 30 minutes" },
  { value: "hourly", label: "Hourly" },
  { value: "daily", label: "Daily" },
  { value: "weekly", label: "Weekly" },
  { value: "monthly", label: "Monthly" },
  { value: "custom", label: "Custom (Cron)" },
];

const DAYS_OF_WEEK = [
  { value: "mon", label: "Mon" },
  { value: "tue", label: "Tue" },
  { value: "wed", label: "Wed" },
  { value: "thu", label: "Thu" },
  { value: "fri", label: "Fri" },
  { value: "sat", label: "Sat" },
  { value: "sun", label: "Sun" },
];

const TIMEZONES = [
  "UTC",
  "America/New_York",
  "America/Chicago",
  "America/Denver",
  "America/Los_Angeles",
  "America/Sao_Paulo",
  "Europe/London",
  "Europe/Paris",
  "Europe/Berlin",
  "Asia/Tokyo",
  "Asia/Shanghai",
  "Asia/Kolkata",
  "Australia/Sydney",
];

function frequencyToCron(
  frequency: string,
  hour: string,
  minute: string,
  selectedDays: string[],
  dayOfMonth: string,
): {
  minute: string;
  hour: string;
  day_of_week: string;
  day_of_month: string;
  month: string;
} {
  switch (frequency) {
    case "every_minute":
      return {
        minute: "*",
        hour: "*",
        day_of_week: "*",
        day_of_month: "*",
        month: "*",
      };
    case "every_5_minutes":
      return {
        minute: "*/5",
        hour: "*",
        day_of_week: "*",
        day_of_month: "*",
        month: "*",
      };
    case "every_15_minutes":
      return {
        minute: "*/15",
        hour: "*",
        day_of_week: "*",
        day_of_month: "*",
        month: "*",
      };
    case "every_30_minutes":
      return {
        minute: "*/30",
        hour: "*",
        day_of_week: "*",
        day_of_month: "*",
        month: "*",
      };
    case "hourly":
      return {
        minute: minute || "0",
        hour: "*",
        day_of_week: "*",
        day_of_month: "*",
        month: "*",
      };
    case "daily":
      return {
        minute: minute || "0",
        hour: hour || "9",
        day_of_week: "*",
        day_of_month: "*",
        month: "*",
      };
    case "weekly":
      return {
        minute: minute || "0",
        hour: hour || "9",
        day_of_week: selectedDays.length > 0 ? selectedDays.join(",") : "mon",
        day_of_month: "*",
        month: "*",
      };
    case "monthly":
      return {
        minute: minute || "0",
        hour: hour || "9",
        day_of_week: "*",
        day_of_month: dayOfMonth || "1",
        month: "*",
      };
    default:
      return {
        minute: "0",
        hour: "*",
        day_of_week: "*",
        day_of_month: "*",
        month: "*",
      };
  }
}

function cronToFrequency(
  min: string,
  hr: string,
  dow: string,
  dom: string,
): {
  frequency: string;
  hour: string;
  minute: string;
  selectedDays: string[];
  dayOfMonth: string;
} {
  if (min === "*" && hr === "*" && dow === "*" && dom === "*") {
    return {
      frequency: "every_minute",
      hour: "0",
      minute: "0",
      selectedDays: [],
      dayOfMonth: "1",
    };
  }
  if (min === "*/5" && hr === "*") {
    return {
      frequency: "every_5_minutes",
      hour: "0",
      minute: "0",
      selectedDays: [],
      dayOfMonth: "1",
    };
  }
  if (min === "*/15" && hr === "*") {
    return {
      frequency: "every_15_minutes",
      hour: "0",
      minute: "0",
      selectedDays: [],
      dayOfMonth: "1",
    };
  }
  if (min === "*/30" && hr === "*") {
    return {
      frequency: "every_30_minutes",
      hour: "0",
      minute: "0",
      selectedDays: [],
      dayOfMonth: "1",
    };
  }
  if (hr === "*" && dow === "*" && dom === "*") {
    return {
      frequency: "hourly",
      hour: "0",
      minute: min,
      selectedDays: [],
      dayOfMonth: "1",
    };
  }
  if (dow === "*" && dom === "*") {
    return {
      frequency: "daily",
      hour: hr,
      minute: min,
      selectedDays: [],
      dayOfMonth: "1",
    };
  }
  if (dom === "*" && dow !== "*") {
    return {
      frequency: "weekly",
      hour: hr,
      minute: min,
      selectedDays: dow.split(","),
      dayOfMonth: "1",
    };
  }
  if (dow === "*" && dom !== "*") {
    return {
      frequency: "monthly",
      hour: hr,
      minute: min,
      selectedDays: [],
      dayOfMonth: dom,
    };
  }
  return {
    frequency: "custom",
    hour: hr,
    minute: min,
    selectedDays: [],
    dayOfMonth: dom,
  };
}

/** Frequencies that require the user to pick a specific time (and thus a timezone). */
const FREQUENCIES_WITH_TIMEZONE = new Set([
  "daily",
  "weekly",
  "monthly",
  "custom",
]);

function needsTimezone(frequency: string): boolean {
  return FREQUENCIES_WITH_TIMEZONE.has(frequency);
}

/** Format a local datetime string for display. */
function formatStartAt(value: string | null): string {
  if (!value) return "Now";
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

function describeSchedule(
  frequency: string,
  hour: string,
  minute: string,
  selectedDays: string[],
  dayOfMonth: string,
  tz: string,
): string {
  const time = `${hour.padStart(2, "0")}:${minute.padStart(2, "0")}`;
  const tzSuffix = needsTimezone(frequency) ? ` (${tz})` : "";
  switch (frequency) {
    case "every_minute":
      return "Every minute";
    case "every_5_minutes":
      return "Every 5 minutes";
    case "every_15_minutes":
      return "Every 15 minutes";
    case "every_30_minutes":
      return "Every 30 minutes";
    case "hourly":
      return `Every hour at minute ${minute}`;
    case "daily":
      return `Daily at ${time}${tzSuffix}`;
    case "weekly":
      return `Weekly on ${selectedDays.join(", ")} at ${time}${tzSuffix}`;
    case "monthly":
      return `Monthly on day ${dayOfMonth} at ${time}${tzSuffix}`;
    case "custom":
      return `Custom cron schedule${tzSuffix}`;
    default:
      return "";
  }
}

export default function ScheduleModal({
  open,
  setOpen,
  flowId,
}: ScheduleModalProps) {
  const { data: existingSchedule, isLoading } = useGetSchedule(flowId, open);
  const { mutateAsync: createSchedule } = useCreateSchedule();
  const { mutateAsync: updateSchedule } = useUpdateSchedule();
  const { mutateAsync: deleteSchedule } = useDeleteSchedule();
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);

  const [isActive, setIsActive] = useState(false);
  const [frequency, setFrequency] = useState("daily");
  const [hour, setHour] = useState("9");
  const [minute, setMinute] = useState("0");
  const [selectedDays, setSelectedDays] = useState<string[]>(["mon"]);
  const [dayOfMonth, setDayOfMonth] = useState("1");
  const [timezone, setTimezone] = useState("UTC");
  const [customMinute, setCustomMinute] = useState("0");
  const [customHour, setCustomHour] = useState("*");
  const [customDow, setCustomDow] = useState("*");
  const [customDom, setCustomDom] = useState("*");
  const [customMonth, setCustomMonth] = useState("*");
  const [startAt, setStartAt] = useState<string | null>(null); // null = now

  const showTimezone = useMemo(() => needsTimezone(frequency), [frequency]);

  useEffect(() => {
    if (existingSchedule) {
      setIsActive(existingSchedule.is_active);
      setTimezone(existingSchedule.timezone);
      const parsed = cronToFrequency(
        existingSchedule.minute,
        existingSchedule.hour,
        existingSchedule.day_of_week,
        existingSchedule.day_of_month,
      );
      setFrequency(parsed.frequency);
      setHour(parsed.hour);
      setMinute(parsed.minute);
      setSelectedDays(parsed.selectedDays);
      setDayOfMonth(parsed.dayOfMonth);
      // Set custom fields
      setCustomMinute(existingSchedule.minute);
      setCustomHour(existingSchedule.hour);
      setCustomDow(existingSchedule.day_of_week);
      setCustomDom(existingSchedule.day_of_month);
      setCustomMonth(existingSchedule.month);
      setStartAt(existingSchedule.start_at ?? null);
    }
  }, [existingSchedule]);

  const handleSave = async () => {
    try {
      let cronFields;
      if (frequency === "custom") {
        cronFields = {
          minute: customMinute,
          hour: customHour,
          day_of_week: customDow,
          day_of_month: customDom,
          month: customMonth,
        };
      } else {
        cronFields = frequencyToCron(
          frequency,
          hour,
          minute,
          selectedDays,
          dayOfMonth,
        );
      }

      const effectiveTimezone = showTimezone ? timezone : "UTC";
      const effectiveStartAt = startAt || undefined;

      if (existingSchedule) {
        await updateSchedule({
          id: existingSchedule.id,
          is_active: isActive,
          ...cronFields,
          timezone: effectiveTimezone,
          start_at: effectiveStartAt,
        });
        setSuccessData({ title: "Schedule updated successfully" });
      } else {
        await createSchedule({
          flow_id: flowId,
          is_active: isActive,
          ...cronFields,
          timezone: effectiveTimezone,
          start_at: effectiveStartAt,
        });
        setSuccessData({ title: "Schedule created successfully" });
      }
      setOpen(false);
    } catch (error: any) {
      setErrorData({
        title: "Failed to save schedule",
        list: [error?.message || "Unknown error"],
      });
    }
  };

  const handleDelete = async () => {
    if (!existingSchedule) return;
    try {
      await deleteSchedule({ id: existingSchedule.id, flow_id: flowId });
      setSuccessData({ title: "Schedule deleted successfully" });
      setOpen(false);
    } catch (error: any) {
      setErrorData({
        title: "Failed to delete schedule",
        list: [error?.message || "Unknown error"],
      });
    }
  };

  const toggleDay = (day: string) => {
    setSelectedDays((prev) =>
      prev.includes(day) ? prev.filter((d) => d !== day) : [...prev, day],
    );
  };

  if (!open) return null;

  return (
    <BaseModal
      open={open}
      setOpen={setOpen}
      size="small-update"
      className="p-4"
    >
      <BaseModal.Header>
        <div className="flex items-center gap-2">
          <IconComponent name="Clock" className="h-5 w-5" />
          <span className="text-base font-semibold">Schedule Flow</span>
        </div>
      </BaseModal.Header>
      <BaseModal.Content>
        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <span className="text-muted-foreground">Loading...</span>
          </div>
        ) : (
          <div className="flex flex-col gap-4 py-2">
            {/* Active Toggle */}
            <div className="flex items-center justify-between">
              <Label className="text-sm font-medium">Enable Schedule</Label>
              <Switch
                checked={isActive}
                onCheckedChange={setIsActive}
                data-testid="schedule-active-toggle"
              />
            </div>

            {/* Frequency */}
            <div className="flex flex-col gap-1.5">
              <Label className="text-sm font-medium">Frequency</Label>
              <Select value={frequency} onValueChange={setFrequency}>
                <SelectTrigger data-testid="schedule-frequency-select">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {FREQUENCY_OPTIONS.map((opt) => (
                    <SelectItem key={opt.value} value={opt.value}>
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Time picker for daily/weekly/monthly/hourly */}
            {["daily", "weekly", "monthly"].includes(frequency) && (
              <div className="flex gap-3">
                <div className="flex flex-1 flex-col gap-1.5">
                  <Label className="text-sm font-medium">Hour</Label>
                  <Input
                    type="number"
                    min={0}
                    max={23}
                    value={hour}
                    onChange={(e) => setHour(e.target.value)}
                    data-testid="schedule-hour-input"
                  />
                </div>
                <div className="flex flex-1 flex-col gap-1.5">
                  <Label className="text-sm font-medium">Minute</Label>
                  <Input
                    type="number"
                    min={0}
                    max={59}
                    value={minute}
                    onChange={(e) => setMinute(e.target.value)}
                    data-testid="schedule-minute-input"
                  />
                </div>
              </div>
            )}

            {frequency === "hourly" && (
              <div className="flex flex-col gap-1.5">
                <Label className="text-sm font-medium">At minute</Label>
                <Input
                  type="number"
                  min={0}
                  max={59}
                  value={minute}
                  onChange={(e) => setMinute(e.target.value)}
                />
              </div>
            )}

            {/* Day of week selector for weekly */}
            {frequency === "weekly" && (
              <div className="flex flex-col gap-1.5">
                <Label className="text-sm font-medium">Days of Week</Label>
                <div className="flex flex-wrap gap-1.5">
                  {DAYS_OF_WEEK.map((day) => (
                    <Button
                      key={day.value}
                      type="button"
                      variant={
                        selectedDays.includes(day.value) ? "default" : "outline"
                      }
                      size="sm"
                      onClick={() => toggleDay(day.value)}
                      data-testid={`schedule-day-${day.value}`}
                    >
                      {day.label}
                    </Button>
                  ))}
                </div>
              </div>
            )}

            {/* Day of month for monthly */}
            {frequency === "monthly" && (
              <div className="flex flex-col gap-1.5">
                <Label className="text-sm font-medium">Day of Month</Label>
                <Input
                  type="number"
                  min={1}
                  max={31}
                  value={dayOfMonth}
                  onChange={(e) => setDayOfMonth(e.target.value)}
                  data-testid="schedule-dom-input"
                />
              </div>
            )}

            {/* Custom cron fields */}
            {frequency === "custom" && (
              <div className="flex flex-col gap-2">
                <Label className="text-sm font-medium">Cron Expression</Label>
                <div className="grid grid-cols-5 gap-2">
                  <div className="flex flex-col gap-1">
                    <span className="text-xs text-muted-foreground">
                      Minute
                    </span>
                    <Input
                      value={customMinute}
                      onChange={(e) => setCustomMinute(e.target.value)}
                    />
                  </div>
                  <div className="flex flex-col gap-1">
                    <span className="text-xs text-muted-foreground">Hour</span>
                    <Input
                      value={customHour}
                      onChange={(e) => setCustomHour(e.target.value)}
                    />
                  </div>
                  <div className="flex flex-col gap-1">
                    <span className="text-xs text-muted-foreground">
                      Day/Month
                    </span>
                    <Input
                      value={customDom}
                      onChange={(e) => setCustomDom(e.target.value)}
                    />
                  </div>
                  <div className="flex flex-col gap-1">
                    <span className="text-xs text-muted-foreground">Month</span>
                    <Input
                      value={customMonth}
                      onChange={(e) => setCustomMonth(e.target.value)}
                    />
                  </div>
                  <div className="flex flex-col gap-1">
                    <span className="text-xs text-muted-foreground">
                      Day/Week
                    </span>
                    <Input
                      value={customDow}
                      onChange={(e) => setCustomDow(e.target.value)}
                    />
                  </div>
                </div>
              </div>
            )}

            {/* Timezone — only for frequencies that reference a specific time */}
            {showTimezone && (
              <div className="flex flex-col gap-1.5">
                <Label className="text-sm font-medium">Timezone</Label>
                <Select value={timezone} onValueChange={setTimezone}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {TIMEZONES.map((tz) => (
                      <SelectItem key={tz} value={tz}>
                        {tz}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}

            {/* Start at */}
            <div className="flex flex-col gap-1.5">
              <Label className="text-sm font-medium">Start at</Label>
              <div className="flex items-center gap-2">
                <Input
                  type="datetime-local"
                  value={startAt ?? ""}
                  onChange={(e) => setStartAt(e.target.value || null)}
                  data-testid="schedule-start-at-input"
                  className="flex-1 dark:[&::-webkit-calendar-picker-indicator]:invert"
                />
                {startAt && (
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => setStartAt(null)}
                  >
                    Now
                  </Button>
                )}
              </div>
              <span className="text-xs text-muted-foreground">
                {startAt
                  ? `Starts at ${formatStartAt(startAt)}`
                  : "Starts immediately"}
              </span>
            </div>

            {/* Schedule description preview */}
            <div className="mt-2 rounded-md border border-border bg-muted p-3">
              <span className="text-sm text-muted-foreground">
                {frequency === "custom"
                  ? `Cron: ${customMinute} ${customHour} ${customDom} ${customMonth} ${customDow} (${timezone})`
                  : describeSchedule(
                      frequency,
                      hour,
                      minute,
                      selectedDays,
                      dayOfMonth,
                      timezone,
                    )}
              </span>
            </div>

            {/* Last run info */}
            {existingSchedule?.last_run_at && (
              <div className="text-xs text-muted-foreground">
                Last run:{" "}
                {new Date(existingSchedule.last_run_at).toLocaleString()} —{" "}
                {existingSchedule.last_run_status}
              </div>
            )}
          </div>
        )}
      </BaseModal.Content>
      <BaseModal.Footer>
        <div className="flex w-full items-center justify-between">
          <div>
            {existingSchedule && (
              <Button
                variant="destructive"
                onClick={handleDelete}
                data-testid="schedule-delete-button"
              >
                Delete
              </Button>
            )}
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleSave} data-testid="schedule-save-button">
              {existingSchedule ? "Update" : "Create"}
            </Button>
          </div>
        </div>
      </BaseModal.Footer>
    </BaseModal>
  );
}
