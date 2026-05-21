import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

// Friendly schedule modes. Each one composes into a 5-field POSIX cron
// expression that the backend's croniter accepts as-is. Users who need
// expressions outside these patterns switch to ``custom`` mode and
// type the cron string themselves.
type Mode = "minutes" | "hours" | "daily" | "weekly" | "custom";

const MINUTE_INTERVALS = [1, 2, 5, 10, 15, 20, 30] as const;
const HOUR_INTERVALS = [1, 2, 3, 4, 6, 8, 12] as const;
const DAYS = [
  { value: "0", labelKey: "triggers.cron.day.sun" },
  { value: "1", labelKey: "triggers.cron.day.mon" },
  { value: "2", labelKey: "triggers.cron.day.tue" },
  { value: "3", labelKey: "triggers.cron.day.wed" },
  { value: "4", labelKey: "triggers.cron.day.thu" },
  { value: "5", labelKey: "triggers.cron.day.fri" },
  { value: "6", labelKey: "triggers.cron.day.sat" },
] as const;

interface ParsedCron {
  mode: Mode;
  minutes: number;
  hours: number;
  daily: { hour: number; minute: number };
  weekly: { day: string; hour: number; minute: number };
  custom: string;
}

const DEFAULTS: ParsedCron = {
  mode: "minutes",
  minutes: 5,
  hours: 1,
  daily: { hour: 9, minute: 0 },
  weekly: { day: "1", hour: 9, minute: 0 },
  custom: "*/5 * * * *",
};

// Parse a cron string back into one of the friendly modes when
// possible. Anything that does not fit one of the recognized patterns
// falls back to ``custom`` so the original expression is preserved.
function parseCron(value: string): ParsedCron {
  const next: ParsedCron = { ...DEFAULTS, custom: value || DEFAULTS.custom };
  const parts = (value ?? "").trim().split(/\s+/);
  if (parts.length !== 5) return next;
  const [m, h, dom, mon, dow] = parts;
  const everyN = (field: string) => {
    const match = field.match(/^\*\/(\d+)$/);
    return match ? Number.parseInt(match[1], 10) : null;
  };

  if (
    h === "*" &&
    dom === "*" &&
    mon === "*" &&
    dow === "*" &&
    everyN(m) !== null
  ) {
    return { ...next, mode: "minutes", minutes: everyN(m)! };
  }
  if (
    m === "0" &&
    dom === "*" &&
    mon === "*" &&
    dow === "*" &&
    everyN(h) !== null
  ) {
    return { ...next, mode: "hours", hours: everyN(h)! };
  }
  const numericMinute = m.match(/^\d{1,2}$/);
  const numericHour = h.match(/^\d{1,2}$/);
  if (numericMinute && numericHour && dom === "*" && mon === "*") {
    if (dow === "*") {
      return {
        ...next,
        mode: "daily",
        daily: {
          hour: Number.parseInt(h, 10),
          minute: Number.parseInt(m, 10),
        },
      };
    }
    if (dow.match(/^[0-6]$/)) {
      return {
        ...next,
        mode: "weekly",
        weekly: {
          day: dow,
          hour: Number.parseInt(h, 10),
          minute: Number.parseInt(m, 10),
        },
      };
    }
  }
  return { ...next, mode: "custom" };
}

function composeCron(state: ParsedCron): string {
  switch (state.mode) {
    case "minutes":
      return `*/${state.minutes} * * * *`;
    case "hours":
      return `0 */${state.hours} * * *`;
    case "daily":
      return `${state.daily.minute} ${state.daily.hour} * * *`;
    case "weekly":
      return `${state.weekly.minute} ${state.weekly.hour} * * ${state.weekly.day}`;
    case "custom":
      return state.custom;
  }
}

interface CronScheduleFieldProps {
  value: string;
  onChange: (cron: string) => void;
  error?: string;
}

export default function CronScheduleField({
  value,
  onChange,
  error,
}: CronScheduleFieldProps) {
  const { t } = useTranslation();

  // ``value`` is the canonical cron string in the parent form. We
  // mirror it into local state on mount and whenever the parent
  // resets (e.g. switching between create and edit). Internal edits
  // recompose the cron and bubble it up via ``onChange``.
  const [state, setState] = useState<ParsedCron>(() => parseCron(value));

  useEffect(() => {
    setState(parseCron(value));
    // We only want to re-sync when ``value`` changes from the parent's
    // perspective, not on every local re-render that pushed a new
    // string up — eslint will warn about onChange, ignore intentionally.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);

  const composed = useMemo(() => composeCron(state), [state]);

  // Push composed cron up whenever state changes.
  useEffect(() => {
    if (composed !== value) onChange(composed);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [composed]);

  const update = (patch: Partial<ParsedCron>) =>
    setState((prev) => ({ ...prev, ...patch }));

  return (
    <div className="flex flex-col gap-2">
      <div className="grid grid-cols-1 gap-2">
        <Select
          value={state.mode}
          onValueChange={(m) => update({ mode: m as Mode })}
        >
          <SelectTrigger data-testid="cron-mode-select">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="minutes">{t("triggers.cron.minutes")}</SelectItem>
            <SelectItem value="hours">{t("triggers.cron.hours")}</SelectItem>
            <SelectItem value="daily">{t("triggers.cron.daily")}</SelectItem>
            <SelectItem value="weekly">{t("triggers.cron.weekly")}</SelectItem>
            <SelectItem value="custom">{t("triggers.cron.custom")}</SelectItem>
          </SelectContent>
        </Select>

        {state.mode === "minutes" && (
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground">
              {t("triggers.cron.everyLabel")}
            </span>
            <Select
              value={String(state.minutes)}
              onValueChange={(v) => update({ minutes: Number.parseInt(v, 10) })}
            >
              <SelectTrigger className="w-[100px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {MINUTE_INTERVALS.map((n) => (
                  <SelectItem key={n} value={String(n)}>
                    {n}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <span className="text-sm text-muted-foreground">
              {t("triggers.cron.minutesUnit")}
            </span>
          </div>
        )}

        {state.mode === "hours" && (
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground">
              {t("triggers.cron.everyLabel")}
            </span>
            <Select
              value={String(state.hours)}
              onValueChange={(v) => update({ hours: Number.parseInt(v, 10) })}
            >
              <SelectTrigger className="w-[100px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {HOUR_INTERVALS.map((n) => (
                  <SelectItem key={n} value={String(n)}>
                    {n}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <span className="text-sm text-muted-foreground">
              {t("triggers.cron.hoursUnit")}
            </span>
          </div>
        )}

        {state.mode === "daily" && (
          <div className="flex items-center gap-2">
            <Label className="text-sm text-muted-foreground" htmlFor="daily-time">
              {t("triggers.cron.atLabel")}
            </Label>
            <Input
              id="daily-time"
              type="time"
              className="w-[140px]"
              value={`${String(state.daily.hour).padStart(2, "0")}:${String(
                state.daily.minute,
              ).padStart(2, "0")}`}
              onChange={(e) => {
                const [h, m] = e.target.value.split(":");
                update({
                  daily: {
                    hour: Number.parseInt(h, 10),
                    minute: Number.parseInt(m, 10),
                  },
                });
              }}
            />
          </div>
        )}

        {state.mode === "weekly" && (
          <div className="flex items-center gap-2">
            <Select
              value={state.weekly.day}
              onValueChange={(day) =>
                update({ weekly: { ...state.weekly, day } })
              }
            >
              <SelectTrigger className="w-[140px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {DAYS.map((d) => (
                  <SelectItem key={d.value} value={d.value}>
                    {t(d.labelKey)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Label className="text-sm text-muted-foreground" htmlFor="weekly-time">
              {t("triggers.cron.atLabel")}
            </Label>
            <Input
              id="weekly-time"
              type="time"
              className="w-[140px]"
              value={`${String(state.weekly.hour).padStart(2, "0")}:${String(
                state.weekly.minute,
              ).padStart(2, "0")}`}
              onChange={(e) => {
                const [h, m] = e.target.value.split(":");
                update({
                  weekly: {
                    ...state.weekly,
                    hour: Number.parseInt(h, 10),
                    minute: Number.parseInt(m, 10),
                  },
                });
              }}
            />
          </div>
        )}

        {state.mode === "custom" && (
          <div className="flex flex-col gap-1">
            <Input
              data-testid="cron-custom-input"
              className="font-mono"
              value={state.custom}
              onChange={(e) => update({ custom: e.target.value })}
              placeholder="*/5 * * * *"
            />
            <span className="text-xs text-muted-foreground">
              {t("triggers.cron.customHint")}
            </span>
          </div>
        )}
      </div>

      <div className="flex items-center gap-2 rounded bg-muted/40 px-2 py-1.5">
        <span className="text-xs text-muted-foreground">
          {t("triggers.cron.previewLabel")}
        </span>
        <code className="text-xs">{composed}</code>
      </div>

      {error && <span className="text-xs text-destructive">{error}</span>}
    </div>
  );
}
