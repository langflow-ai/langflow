import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
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
import { useGetRefreshFlowsQuery } from "@/controllers/API/queries/flows/use-get-refresh-flows-query";
import { useGetFoldersQuery } from "@/controllers/API/queries/folders/use-get-folders";
import {
  useGetTriggers,
  usePostTrigger,
} from "@/controllers/API/queries/triggers";
import useAlertStore from "@/stores/alertStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useFolderStore } from "@/stores/foldersStore";

/**
 * Curated IANA timezone list. Mirrors
 * ``lfx/components/triggers/constants.py::COMMON_TIMEZONES`` — kept
 * in sync manually because the frontend has no other source for
 * this canvas-side default. Users who need a zone outside this set
 * type its IANA name into the canvas component instead.
 */
const COMMON_TIMEZONES = [
  "UTC",
  "America/New_York",
  "America/Chicago",
  "America/Denver",
  "America/Los_Angeles",
  "America/Sao_Paulo",
  "America/Argentina/Buenos_Aires",
  "America/Mexico_City",
  "Europe/London",
  "Europe/Berlin",
  "Europe/Paris",
  "Europe/Madrid",
  "Asia/Tokyo",
  "Asia/Shanghai",
  "Asia/Kolkata",
  "Australia/Sydney",
] as const;

const MINUTE_INTERVAL_MAX = 59;
const HOUR_INTERVAL_MAX = 23;

// Uniform sizing for every form control inside the modal. Inputs and
// SelectTriggers in shadcn ship at different default heights (h-9 vs
// h-8); we pin them both to the same value so paired rows align.
const CONTROL_HEIGHT_CLASS = "h-9";

interface TriggerCreateModalProps {
  open: boolean;
  setOpen: (open: boolean) => void;
}

/**
 * "New Trigger" modal — single Dialog, no stepper.
 *
 * Two halves: (1) target flow picker (lists user-owned flows; flows
 * that already have a CronTrigger appear disabled with a "trigger
 * exists" suffix), (2) schedule controls that mirror the canvas
 * component one-for-one (Schedule toggle + interval picker OR
 * time-of-day + timezone).
 *
 * The submit hits ``POST /api/v1/triggers``; the backend lifecycle
 * hook enqueues the first trigger_job at the next fire time, so the
 * row in the parent ``/triggers`` page appears immediately.
 */
export default function TriggerCreateModal({
  open,
  setOpen,
}: TriggerCreateModalProps) {
  const { t } = useTranslation();
  const setErrorData = useAlertStore((s) => s.setErrorData);
  const setSuccessData = useAlertStore((s) => s.setSuccessData);

  // We use the same data sources the home page uses:
  //
  // * ``useGetRefreshFlowsQuery({get_all, remove_example_flows})`` —
  //   the bulk flow list. ``remove_example_flows=true`` filters out
  //   any flow in the system "Starter Projects" (plural) folder
  //   server-side.
  // * ``useGetFoldersQuery`` — list of folders the user owns. The
  //   backend ``GET /projects/`` already excludes the system starter
  //   folder, so its return is *exactly* the navigable-folder set.
  //
  // Joining the two on the frontend (flow.folder_id ∈ user_folders)
  // is the same predicate the home page's folder sidebar uses to
  // decide which folders to render — "any flow the user can navigate
  // to". This avoids the user_id-based filter that broke in
  // AUTO_LOGIN mode when a flow's user_id stayed NULL after the user
  // edited a cloned template.
  const flows = useFlowsManagerStore((s) => s.flows);
  useGetRefreshFlowsQuery(
    { get_all: true, remove_example_flows: true },
    { enabled: open && (flows === undefined || flows.length === 0) },
  );
  useGetFoldersQuery();
  const folders = useFolderStore((s) => s.folders);
  const { data: existingTriggers } = useGetTriggers({ enabled: open });

  // Form state. Defaults match the canvas component initial values.
  const [flowId, setFlowId] = useState<string>("");
  const [atSpecificTime, setAtSpecificTime] = useState(false);
  const [intervalValue, setIntervalValue] = useState(5);
  const [intervalUnit, setIntervalUnit] = useState<"minutes" | "hours">(
    "minutes",
  );
  const [timeOfDay, setTimeOfDay] = useState("09:00");
  const [timezone, setTimezone] = useState<string>("UTC");

  // Reset to defaults each time the modal opens — avoids carrying
  // state across separate create flows.
  useEffect(() => {
    if (open) {
      setFlowId("");
      setAtSpecificTime(false);
      setIntervalValue(5);
      setIntervalUnit("minutes");
      setTimeOfDay("09:00");
      setTimezone("UTC");
    }
  }, [open]);

  // Filter + decorate flows for the picker. "Mine" = ``folder_id``
  // belongs to a folder the user can navigate to.
  const flowOptions = useMemo(() => {
    const userFolderIds = new Set((folders ?? []).map((f) => f.id));
    const triggerFlowIds = new Set(
      (existingTriggers ?? []).map((t) => t.flow_id),
    );
    return (flows ?? [])
      .filter((f) => !f.is_component)
      .filter((f) => !f.folder_id || userFolderIds.has(f.folder_id))
      .map((f) => ({
        id: f.id,
        name: f.name,
        hasTrigger: triggerFlowIds.has(f.id),
      }))
      .sort((a, b) => a.name.localeCompare(b.name));
  }, [flows, folders, existingTriggers]);

  const { mutate: createTrigger, isPending } = usePostTrigger({
    onSuccess: () => {
      setSuccessData({ title: t("triggers.createSuccess") });
      setOpen(false);
    },
    onError: (err) => {
      const detail =
        // Surface the server-side detail (singleton conflict, bad
        // cron / tz, etc.) instead of a generic "request failed".
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail ?? String((err as Error)?.message ?? err);
      setErrorData({ title: t("triggers.createError"), list: [detail] });
    },
  });

  const isValid = useMemo(() => {
    if (!flowId) return false;
    if (atSpecificTime) {
      // Defensive HH:MM check — backend re-validates, but blocking
      // submit on obvious garbage saves a round-trip.
      return /^\d{1,2}:\d{2}$/.test(timeOfDay) && !!timezone;
    }
    const max =
      intervalUnit === "minutes" ? MINUTE_INTERVAL_MAX : HOUR_INTERVAL_MAX;
    return intervalValue >= 1 && intervalValue <= max;
  }, [
    flowId,
    atSpecificTime,
    timeOfDay,
    timezone,
    intervalValue,
    intervalUnit,
  ]);

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!isValid) return;
    createTrigger({
      flow_id: flowId,
      at_specific_time: atSpecificTime,
      interval_value: intervalValue,
      interval_unit: intervalUnit,
      time_of_day: timeOfDay,
      timezone,
      max_attempts: 3,
    });
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>{t("triggers.createTitle")}</DialogTitle>
        </DialogHeader>
        <form onSubmit={onSubmit} className="flex flex-col gap-3 py-1">
          {/* ---------- flow picker ---------- */}
          <FieldRow label={t("triggers.field.flow")} htmlFor="flow_id">
            <Select value={flowId} onValueChange={setFlowId}>
              <SelectTrigger
                id="flow_id"
                className={CONTROL_HEIGHT_CLASS}
                data-testid="trigger-flow-select"
              >
                <SelectValue
                  placeholder={t("triggers.field.flowPlaceholder")}
                />
              </SelectTrigger>
              <SelectContent>
                {flowOptions.length === 0 ? (
                  <div className="px-3 py-2 text-xs text-muted-foreground">
                    {t("triggers.field.flowEmpty")}
                  </div>
                ) : (
                  flowOptions.map((flow) => (
                    <SelectItem
                      key={flow.id}
                      value={flow.id}
                      disabled={flow.hasTrigger}
                    >
                      <span>{flow.name}</span>
                      {flow.hasTrigger && (
                        <span className="ml-2 text-xs text-muted-foreground">
                          · {t("triggers.field.flowAlreadyHasTrigger")}
                        </span>
                      )}
                    </SelectItem>
                  ))
                )}
              </SelectContent>
            </Select>
          </FieldRow>

          {/* ---------- schedule toggle ---------- */}
          <div className="flex items-center justify-between rounded-md border border-input px-3 py-1.5">
            <Label
              htmlFor="at_specific_time"
              className="cursor-pointer text-sm"
            >
              {t("triggers.field.atSpecificTime")}
            </Label>
            <Switch
              id="at_specific_time"
              checked={atSpecificTime}
              onCheckedChange={setAtSpecificTime}
            />
          </div>

          {/* ---------- branch fields (always 2-col grid, equal widths) ---------- */}
          {!atSpecificTime ? (
            <div className="grid grid-cols-2 gap-3">
              <FieldRow
                label={t("triggers.field.every")}
                htmlFor="interval_value"
              >
                <Input
                  id="interval_value"
                  type="number"
                  min={1}
                  max={
                    intervalUnit === "minutes"
                      ? MINUTE_INTERVAL_MAX
                      : HOUR_INTERVAL_MAX
                  }
                  value={intervalValue}
                  onChange={(e) =>
                    setIntervalValue(Number.parseInt(e.target.value || "1", 10))
                  }
                  className={CONTROL_HEIGHT_CLASS}
                  data-testid="trigger-interval-value"
                />
              </FieldRow>
              <FieldRow
                label={t("triggers.field.unit")}
                htmlFor="interval_unit"
              >
                <Select
                  value={intervalUnit}
                  onValueChange={(v) =>
                    setIntervalUnit(v as "minutes" | "hours")
                  }
                >
                  <SelectTrigger
                    id="interval_unit"
                    className={CONTROL_HEIGHT_CLASS}
                    data-testid="trigger-interval-unit"
                  >
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="minutes">
                      {t("triggers.unit.minutes")}
                    </SelectItem>
                    <SelectItem value="hours">
                      {t("triggers.unit.hours")}
                    </SelectItem>
                  </SelectContent>
                </Select>
              </FieldRow>
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-3">
              <FieldRow
                label={t("triggers.field.timeOfDay")}
                htmlFor="time_of_day"
              >
                <Input
                  id="time_of_day"
                  type="time"
                  value={timeOfDay}
                  onChange={(e) => setTimeOfDay(e.target.value)}
                  className={CONTROL_HEIGHT_CLASS}
                  data-testid="trigger-time-of-day"
                />
              </FieldRow>
              <FieldRow label={t("triggers.field.timezone")} htmlFor="timezone">
                <Select value={timezone} onValueChange={setTimezone}>
                  <SelectTrigger
                    id="timezone"
                    className={CONTROL_HEIGHT_CLASS}
                    data-testid="trigger-timezone"
                  >
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {COMMON_TIMEZONES.map((tz) => (
                      <SelectItem key={tz} value={tz}>
                        {tz}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </FieldRow>
            </div>
          )}

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              size="md"
              onClick={() => setOpen(false)}
            >
              {t("triggers.cancel")}
            </Button>
            <Button
              type="submit"
              variant="default"
              size="md"
              loading={isPending}
              disabled={!isValid}
              data-testid="trigger-create-submit"
            >
              <ForwardedIconComponent name="Plus" className="h-4 w-4" />
              {t("triggers.create")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

/**
 * Label-above-control row, used for every field in the modal so the
 * vertical rhythm and label styling stay identical across rows.
 * Extracted because in-line JSX would otherwise duplicate the same
 * ``<div class="flex flex-col gap-1.5">`` wrapper five times.
 */
function FieldRow({
  label,
  htmlFor,
  children,
}: {
  label: string;
  htmlFor: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={htmlFor} className="text-sm">
        {label}
      </Label>
      {children}
    </div>
  );
}
