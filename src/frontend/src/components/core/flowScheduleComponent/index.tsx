import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
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
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { useGetSchedules } from "@/controllers/API/queries/schedules/use-get-schedules";
import { useCreateSchedule } from "@/controllers/API/queries/schedules/use-create-schedule";
import { useUpdateSchedule } from "@/controllers/API/queries/schedules/use-update-schedule";
import { useDeleteSchedule } from "@/controllers/API/queries/schedules/use-delete-schedule";
import useAlertStore from "@/stores/alertStore";
import type { FlowScheduleType } from "@/types/schedules";

const DAYS_OF_WEEK = [
  { value: 0, label: "Mon" },
  { value: 1, label: "Tue" },
  { value: 2, label: "Wed" },
  { value: 3, label: "Thu" },
  { value: 4, label: "Fri" },
  { value: 5, label: "Sat" },
  { value: 6, label: "Sun" },
];

const COMMON_TIMEZONES = [
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
  "Pacific/Auckland",
];

const REPEAT_OPTIONS = [
  { value: "daily", label: "Daily" },
  { value: "weekdays", label: "Weekdays (Mon-Fri)" },
  { value: "weekly", label: "Weekly" },
  { value: "custom", label: "Custom" },
];

function buildCronExpression(
  days: number[],
  times: string[],
  repeatFrequency: string,
): string {
  if (times.length === 0) {
    return "0 0 * * *";
  }

  // Parse times to get unique minutes and hours
  const minutes = new Set<number>();
  const hours = new Set<number>();
  for (const t of times) {
    const [h, m] = t.split(":").map(Number);
    hours.add(h);
    minutes.add(m);
  }

  const minutePart = [...minutes].sort((a, b) => a - b).join(",");
  const hourPart = [...hours].sort((a, b) => a - b).join(",");

  let dayOfWeekPart = "*";
  if (repeatFrequency === "weekdays") {
    dayOfWeekPart = "1,2,3,4,5";
  } else if (repeatFrequency === "weekly" || repeatFrequency === "custom") {
    if (days.length > 0 && days.length < 7) {
      // Cron uses 0=Sunday, but our UI uses 0=Monday
      // Convert: UI Monday(0)->Cron 1, UI Sunday(6)->Cron 0
      const cronDays = days.map((d) => (d + 1) % 7);
      dayOfWeekPart = cronDays.sort((a, b) => a - b).join(",");
    }
  }

  return `${minutePart} ${hourPart} * * ${dayOfWeekPart}`;
}

function parseCronExpression(cron: string): {
  days: number[];
  times: string[];
} {
  const parts = cron.split(" ");
  if (parts.length !== 5) return { days: [], times: [] };

  const [minutePart, hourPart, , , dayOfWeekPart] = parts;

  const minutes = minutePart === "*" ? [0] : minutePart.split(",").map(Number);
  const hours = hourPart === "*" ? [0] : hourPart.split(",").map(Number);

  const times: string[] = [];
  for (const h of hours) {
    for (const m of minutes) {
      times.push(`${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`);
    }
  }

  let days: number[] = [];
  if (dayOfWeekPart !== "*") {
    // Convert from cron (0=Sunday) to UI (0=Monday)
    const cronDays = dayOfWeekPart.split(",").map(Number);
    days = cronDays.map((d) => (d === 0 ? 6 : d - 1));
  }

  return { days, times };
}

type FlowScheduleComponentProps = {
  flowId: string;
};

export default function FlowScheduleComponent({
  flowId,
}: FlowScheduleComponentProps) {
  const { data: schedules, isLoading } = useGetSchedules(flowId);
  const { mutate: createSchedule } = useCreateSchedule();
  const { mutate: updateSchedule } = useUpdateSchedule();
  const { mutate: deleteSchedule } = useDeleteSchedule();
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);

  const existingSchedule = schedules?.[0] ?? null;

  const [isActive, setIsActive] = useState(false);
  const [selectedDays, setSelectedDays] = useState<number[]>([]);
  const [timeInputs, setTimeInputs] = useState<string[]>([""]);
  const [selectedTimezone, setSelectedTimezone] = useState("UTC");
  const [repeatFrequency, setRepeatFrequency] = useState("daily");
  const [cronPreview, setCronPreview] = useState("0 0 * * *");
  const [isSaving, setIsSaving] = useState(false);

  // Load existing schedule
  useEffect(() => {
    if (existingSchedule) {
      setIsActive(existingSchedule.is_active);
      setSelectedTimezone(existingSchedule.timezone);
      setRepeatFrequency(existingSchedule.repeat_frequency ?? "daily");

      if (existingSchedule.times_of_day?.length) {
        setTimeInputs(existingSchedule.times_of_day);
      }
      if (existingSchedule.days_of_week?.length) {
        setSelectedDays(existingSchedule.days_of_week);
      }

      setCronPreview(existingSchedule.cron_expression);
    }
  }, [existingSchedule]);

  // Rebuild cron preview whenever inputs change
  useEffect(() => {
    const validTimes = timeInputs.filter((t) => /^\d{2}:\d{2}$/.test(t));
    if (validTimes.length > 0) {
      const cron = buildCronExpression(
        selectedDays,
        validTimes,
        repeatFrequency,
      );
      setCronPreview(cron);
    }
  }, [selectedDays, timeInputs, repeatFrequency]);

  // Pre-select days based on repeat frequency
  useEffect(() => {
    if (repeatFrequency === "daily") {
      setSelectedDays([0, 1, 2, 3, 4, 5, 6]);
    } else if (repeatFrequency === "weekdays") {
      setSelectedDays([0, 1, 2, 3, 4]);
    }
  }, [repeatFrequency]);

  const toggleDay = (day: number) => {
    setSelectedDays((prev) =>
      prev.includes(day) ? prev.filter((d) => d !== day) : [...prev, day],
    );
  };

  const addTimeSlot = () => {
    setTimeInputs((prev) => [...prev, ""]);
  };

  const removeTimeSlot = (index: number) => {
    setTimeInputs((prev) => prev.filter((_, i) => i !== index));
  };

  const updateTimeSlot = (index: number, value: string) => {
    setTimeInputs((prev) => {
      const updated = [...prev];
      updated[index] = value;
      return updated;
    });
  };

  const handleSave = () => {
    const validTimes = timeInputs.filter((t) => /^\d{2}:\d{2}$/.test(t));
    if (validTimes.length === 0) {
      setErrorData({ title: "Please add at least one valid time" });
      return;
    }

    const cronExpression = buildCronExpression(
      selectedDays,
      validTimes,
      repeatFrequency,
    );

    setIsSaving(true);

    if (existingSchedule) {
      updateSchedule(
        {
          id: existingSchedule.id,
          flow_id: flowId,
          is_active: isActive,
          cron_expression: cronExpression,
          timezone: selectedTimezone,
          days_of_week: selectedDays,
          times_of_day: validTimes,
          repeat_frequency: repeatFrequency,
        },
        {
          onSuccess: () => {
            setIsSaving(false);
            setSuccessData({ title: "Schedule updated" });
          },
          onError: () => {
            setIsSaving(false);
            setErrorData({ title: "Failed to update schedule" });
          },
        },
      );
    } else {
      createSchedule(
        {
          flow_id: flowId,
          is_active: isActive,
          cron_expression: cronExpression,
          timezone: selectedTimezone,
          days_of_week: selectedDays,
          times_of_day: validTimes,
          repeat_frequency: repeatFrequency,
        },
        {
          onSuccess: () => {
            setIsSaving(false);
            setSuccessData({ title: "Schedule created" });
          },
          onError: () => {
            setIsSaving(false);
            setErrorData({ title: "Failed to create schedule" });
          },
        },
      );
    }
  };

  const handleDelete = () => {
    if (!existingSchedule) return;
    setIsSaving(true);
    deleteSchedule(
      { id: existingSchedule.id, flow_id: flowId },
      {
        onSuccess: () => {
          setIsSaving(false);
          setIsActive(false);
          setSelectedDays([]);
          setTimeInputs([""]);
          setRepeatFrequency("daily");
          setSelectedTimezone("UTC");
          setSuccessData({ title: "Schedule deleted" });
        },
        onError: () => {
          setIsSaving(false);
          setErrorData({ title: "Failed to delete schedule" });
        },
      },
    );
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-4 text-sm text-muted-foreground">
        Loading schedule...
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Active toggle */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-mmd font-medium">Enable Schedule</span>
            <ForwardedIconComponent
              name="Clock"
              className="text-muted-foreground !h-4 !w-4"
            />
          </div>
          <p className="mt-1 text-xs font-normal text-muted-foreground/70">
            Automatically run this flow on a recurring schedule.
          </p>
        </div>
        <Switch
          checked={isActive}
          onCheckedChange={setIsActive}
          className="data-[state=checked]:bg-primary ml-auto"
          data-testid="schedule-active-switch"
        />
      </div>

      {/* Schedule configuration (only shown when active) */}
      {isActive && (
        <div className="flex flex-col gap-4 rounded-md border border-input p-3">
          {/* Repeat frequency */}
          <div className="flex flex-col gap-1.5">
            <Label className="text-mmd font-medium">Repeat</Label>
            <Select value={repeatFrequency} onValueChange={setRepeatFrequency}>
              <SelectTrigger
                className="w-full"
                data-testid="schedule-repeat-select"
              >
                <SelectValue placeholder="Select frequency" />
              </SelectTrigger>
              <SelectContent>
                {REPEAT_OPTIONS.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Days of week (for weekly/custom) */}
          {(repeatFrequency === "weekly" || repeatFrequency === "custom") && (
            <div className="flex flex-col gap-1.5">
              <Label className="text-mmd font-medium">Days</Label>
              <div className="flex flex-wrap gap-1.5">
                {DAYS_OF_WEEK.map((day) => (
                  <button
                    key={day.value}
                    type="button"
                    onClick={() => toggleDay(day.value)}
                    data-testid={`schedule-day-${day.label.toLowerCase()}`}
                    className={`rounded-md border px-2.5 py-1 text-xs font-medium transition-colors ${
                      selectedDays.includes(day.value)
                        ? "border-primary bg-primary text-primary-foreground"
                        : "border-input bg-background text-muted-foreground hover:bg-muted"
                    }`}
                  >
                    {day.label}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Times of day */}
          <div className="flex flex-col gap-1.5">
            <Label className="text-mmd font-medium">Time(s)</Label>
            <div className="flex flex-col gap-2">
              {timeInputs.map((time, index) => (
                <div key={index} className="flex items-center gap-2">
                  <Input
                    type="time"
                    value={time}
                    onChange={(e) => updateTimeSlot(index, e.target.value)}
                    className="w-full font-normal"
                    data-testid={`schedule-time-${index}`}
                  />
                  {timeInputs.length > 1 && (
                    <Button
                      variant="ghost"
                      size="icon"
                      type="button"
                      className="h-8 w-8 shrink-0"
                      onClick={() => removeTimeSlot(index)}
                      data-testid={`schedule-remove-time-${index}`}
                    >
                      <ForwardedIconComponent name="X" className="!h-4 !w-4" />
                    </Button>
                  )}
                </div>
              ))}
              <Button
                variant="outline"
                size="sm"
                type="button"
                onClick={addTimeSlot}
                className="w-fit"
                data-testid="schedule-add-time"
              >
                <ForwardedIconComponent
                  name="Plus"
                  className="mr-1.5 !h-3.5 !w-3.5"
                />
                Add time
              </Button>
            </div>
          </div>

          {/* Timezone */}
          <div className="flex flex-col gap-1.5">
            <Label className="text-mmd font-medium">Timezone</Label>
            <Select
              value={selectedTimezone}
              onValueChange={setSelectedTimezone}
            >
              <SelectTrigger
                className="w-full"
                data-testid="schedule-timezone-select"
              >
                <SelectValue placeholder="Select timezone" />
              </SelectTrigger>
              <SelectContent>
                {COMMON_TIMEZONES.map((tz) => (
                  <SelectItem key={tz} value={tz}>
                    {tz.replace(/_/g, " ")}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Cron expression preview */}
          <div className="flex flex-col gap-1.5">
            <Label className="text-xs font-medium text-muted-foreground">
              Cron Expression
            </Label>
            <code className="rounded bg-muted px-2 py-1 font-mono text-xs">
              {cronPreview}
            </code>
          </div>

          {/* Last run status */}
          {existingSchedule?.last_run_at && (
            <div className="rounded border border-input bg-muted/50 px-3 py-2 text-xs text-muted-foreground">
              <span className="font-medium">Last run:</span>{" "}
              {new Date(existingSchedule.last_run_at).toLocaleString()} -{" "}
              <span
                className={
                  existingSchedule.last_run_status === "completed"
                    ? "text-green-600"
                    : "text-destructive"
                }
              >
                {existingSchedule.last_run_status}
              </span>
              {existingSchedule.last_run_error && (
                <p className="mt-1 text-destructive">
                  {existingSchedule.last_run_error}
                </p>
              )}
            </div>
          )}

          {/* Actions */}
          <div className="flex items-center gap-2">
            <Button
              variant="default"
              size="sm"
              type="button"
              loading={isSaving}
              onClick={handleSave}
              data-testid="schedule-save"
            >
              {existingSchedule ? "Update Schedule" : "Create Schedule"}
            </Button>
            {existingSchedule && (
              <Button
                variant="outline"
                size="sm"
                type="button"
                loading={isSaving}
                onClick={handleDelete}
                data-testid="schedule-delete"
              >
                Delete
              </Button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
